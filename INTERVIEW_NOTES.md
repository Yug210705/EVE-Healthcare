# EVE Healthcare Backend — Interview Notes

This document provides concise explanations for the engineering decisions made in this assessment. It acts as a reference for any follow-up interview questions.

**1. Why FastAPI?**
FastAPI provides high performance (via Starlette/Pydantic), automatic OpenAPI/Swagger documentation, and excellent developer experience with type hints. It fits the requirement for a modern, production-minded REST API without the boilerplate of Django.

**2. Why PostgreSQL?**
PostgreSQL is a robust relational database that provides strong ACID guarantees. It offers essential features used in this project like `JSONB` (for storing webhook payloads), exact `NUMERIC` types, `UUID` primary keys, and robust transaction locking (`SELECT FOR UPDATE`), which are critical for financial/booking data.

**3. Why SQLAlchemy?**
SQLAlchemy 2.0 is the industry standard ORM for Python. It provides strong type safety, explicit transaction control, and prevents SQL injection. Using its ORM models ensures our application logic strongly aligns with our database schema.

**4. Why Alembic?**
Alembic is the standard migration tool for SQLAlchemy. It allows us to track database schema changes iteratively in source control, making it possible to deploy changes predictably rather than relying on manual SQL scripts or `create_all()`.

**5. Why JWT?**
JSON Web Tokens (JWT) allow for stateless authentication. The server doesn't need to look up a session ID in the database for every request; it simply verifies the token's cryptographic signature, reducing database load and making the API easily scalable.

**6. Why separate models and schemas?**
SQLAlchemy models represent the physical database tables, while Pydantic schemas represent the API contracts (DTOs). Separating them prevents accidental data exposure (like returning a `hashed_password`) and allows the API to evolve independently of the database schema (e.g., accepting only `test_id` and deriving `amount` internally).

**7. Why a service layer?**
While simple CRUD apps can put logic in routes, a booking/payment system has complex rules (e.g., state transitions, idempotency checks, double-payment prevention). The service layer isolates this business logic, making it easier to test in isolation and keeping the route handlers thin. We intentionally avoided a "Repository" layer because SQLAlchemy 2.0 already acts as a robust data mapper, and adding a wrapper would have been unnecessary over-engineering for this scope.

**8. How does booking state transition work?**
Bookings start in a `PENDING` state. State transitions are strictly controlled by business events in the service layer (e.g., successful payment, failed payment, cancellation). `CONFIRMED`, `FAILED`, and `CANCELLED` are defined as terminal states. The service explicitly checks and rejects transitions out of a terminal state.

**9. How does payment processing work?**
The client requests a payment simulation for a `PENDING` booking. The service locks the booking row (`SELECT FOR UPDATE`), verifies the user owns it, checks that it's not already paid, and derives the amount from the database (not the client). It creates a `Payment` record and updates the `Booking` status in the same database transaction, ensuring they never fall out of sync.

**10. How does webhook idempotency work?**
It uses a two-layer defense strategy:
1. **Event Level**: A `UNIQUE` constraint on `webhook_events.provider_event_id`. If the exact same webhook is delivered twice, the second attempt fails at the database level.
2. **Payment Level**: A `UNIQUE` constraint on `payments.provider_reference`. If a provider sends a *new* event ID for a payment we've already processed, the duplicate payment is blocked.

**11. How does the database prevent duplicate webhook processing?**
We use an **INSERT-first** strategy. We immediately try to `INSERT` the webhook event into the database inside a `SAVEPOINT` (`db.begin_nested()`). If it's a duplicate, PostgreSQL throws an `IntegrityError`, which we catch and safely ignore. This relies on the database's ACID guarantees rather than an application-level `if exists` check.

**12. What happens if two identical webhooks arrive simultaneously?**
Because of the INSERT-first strategy, they will both attempt to `INSERT` the same `event_id`. PostgreSQL will lock the index, allow one to succeed, and throw an `IntegrityError` for the other. The application handles the error gracefully and returns 200 without processing the second webhook.

**13. What happens if payment succeeds but the client times out?**
The transaction is committed to the database *before* the HTTP response is sent. The database state is safe (`Booking` is `CONFIRMED`, `Payment` is `SUCCESS`). When the client retries, they will see the booking is already confirmed, or if they retry the payment endpoint, they will receive a `409 Conflict` (double-payment prevention).

**14. What happens if a webhook is retried?**
If it's the exact same webhook (same `event_id`), it is caught by Layer 1 (Event ID constraint) and ignored. If it's a retry with a new `event_id` but the same `payment_reference`, it is caught by Layer 2 (Payment Reference constraint). If it tries to change a booking that is already `CONFIRMED` to `FAILED` (e.g., a delayed, out-of-order webhook), the state transition check blocks it.

**15. What happens if a user tries to access another user's booking?**
The service layer explicitly checks `if booking.user_id != user_id:` and raises a `403 Forbidden` error. This object-level authorization ensures users only see and modify their own data.

**16. Why are monetary values represented using Decimal/Numeric?**
Floating-point numbers (e.g., `float`) cannot accurately represent base-10 decimals, leading to rounding errors (e.g., `0.1 + 0.2 = 0.30000000000000004`). In financial transactions, this is unacceptable. `DECIMAL`/`NUMERIC` types store exact precision.

**17. What indexes were added and why?**
- `users.email`: For fast login lookups and enforcing uniqueness.
- `diagnostic_centres.city`: To allow fast filtering by city.
- `diagnostic_tests.centre_id`: Foreign key index to quickly fetch all tests for a centre.
- `bookings.user_id`: To quickly list a user's bookings.
- `bookings.status`: For querying bookings by state (e.g., finding all pending bookings).
- `payments.booking_id`: To quickly find payments associated with a booking.

**18. What would you change for production scale?**
- Implement cursor-based pagination instead of offset/limit.
- Move webhook processing to a background task queue (e.g., Celery or AWS SQS) to decouple HTTP response times from database processing.
- Add Redis for caching the diagnostic centres and tests, as they change infrequently.
- Set up read replicas for the database if read-heavy.

**19. What would you change if integrating a real payment provider?**
- Add cryptographic signature verification to the webhook endpoint (e.g., checking `Stripe-Signature` headers) to ensure payloads actually came from the provider.
- Store the provider's specific metadata (like receipt URLs or failure codes) in the `Payment` or `WebhookEvent` table.

**20. What trade-offs did you intentionally make because this was a 3–4 hour assessment?**
- Omitted an explicit Repository layer, favoring inline SQLAlchemy 2.0 queries for simplicity.
- Did not set up a background task queue for webhooks, instead processing them synchronously.
- Did not implement soft deletes, keeping the database schema simpler.
- Used a mock payment simulation controlled via a `simulate` flag rather than integrating a sandbox SDK.
