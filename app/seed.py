"""
Seed script — populates diagnostic centres and tests for local development.
Run: python -m app.seed
"""

import logging
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.diagnostic_centre import DiagnosticCentre
from app.models.diagnostic_test import DiagnosticTest

logger = logging.getLogger(__name__)

SEED_DATA = [
    {
        "name": "HealthFirst Diagnostics",
        "address": "42 MG Road, Andheri East",
        "city": "Mumbai",
        "tests": [
            ("Complete Blood Count", "Measures RBC, WBC, hemoglobin, hematocrit, and platelets", Decimal("500.00")),
            ("Lipid Profile", "Total cholesterol, HDL, LDL, triglycerides", Decimal("800.00")),
            ("Thyroid Panel", "TSH, T3, T4 levels", Decimal("1200.00")),
        ],
    },
    {
        "name": "MedScan Labs",
        "address": "15 Connaught Place, Block B",
        "city": "Delhi",
        "tests": [
            ("Liver Function Test", "ALT, AST, bilirubin, albumin", Decimal("900.00")),
            ("Kidney Function Test", "Creatinine, BUN, eGFR", Decimal("750.00")),
            ("Vitamin D", "25-hydroxy vitamin D level", Decimal("1500.00")),
        ],
    },
    {
        "name": "CarePoint Diagnostics",
        "address": "88 Koramangala 4th Block",
        "city": "Bangalore",
        "tests": [
            ("HbA1c", "Glycated hemoglobin — 3-month blood sugar average", Decimal("600.00")),
            ("Iron Studies", "Serum iron, ferritin, TIBC", Decimal("850.00")),
            ("Calcium Test", "Serum calcium levels", Decimal("400.00")),
        ],
    },
]


def seed():
    db = SessionLocal()
    try:
        existing = db.execute(select(DiagnosticCentre)).scalars().first()
        if existing:
            logger.info("Seed data already exists, skipping")
            return

        for centre_data in SEED_DATA:
            centre = DiagnosticCentre(
                name=centre_data["name"],
                address=centre_data["address"],
                city=centre_data["city"],
            )
            db.add(centre)
            db.flush()  # Get centre.id for FK

            for test_name, test_desc, test_price in centre_data["tests"]:
                test = DiagnosticTest(
                    centre_id=centre.id,
                    name=test_name,
                    description=test_desc,
                    price=test_price,
                )
                db.add(test)

        db.commit()
        logger.info("Seed data inserted: %d centres", len(SEED_DATA))
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
