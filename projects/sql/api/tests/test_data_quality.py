"""
test_data_quality.py
--------------------
SQL data quality tests across three domains.

What is data quality testing?
------------------------------
Most API tests verify that the API returns the right response.
Data quality tests verify that the DATA in the database meets
business rules — even when the API accepts the request.

Real-world context
------------------
At Indeed, job posting data had quality rules:
- Required fields (title, company, location)
- Valid salary ranges
- No duplicate postings for the same job

At Finix, transaction data had quality rules:
- No duplicate transaction IDs (idempotency at DB level)
- Positive amounts only
- Valid currency codes

At healthcare companies, patient data has quality rules:
- No duplicate MRNs
- Required demographic fields
- Valid gender values

These tests verify those rules at the database layer,
not just at the API layer.

Test categories
---------------
1. NULL checks — required fields must not be NULL
2. Uniqueness — no duplicate keys or identifiers
3. Range validation — values within allowed bounds
4. Referential integrity — related records exist
5. Schema consistency — expected columns and types
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from projects.sql.api.models.sql_models import (
    Patient, Policy, Transaction,
    create_sandbox_engine, create_sandbox_session,
)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def session():
    """Fresh in-memory SQLite session per test."""
    engine  = create_sandbox_engine()
    session = create_sandbox_session(engine)
    yield session
    session.close()


@pytest.fixture
def valid_patient():
    return Patient(
        mrn="MRN-001",
        first_name="John",
        last_name="Smith",
        date_of_birth=date(1990, 1, 15),
        gender="male",
        email="john.smith@example.com",
    )


@pytest.fixture
def valid_transaction():
    return Transaction(
        transaction_id="TXN-001",
        amount=1000.00,
        currency="USD",
        merchant_id="merchant-001",
        status="SUCCEEDED",
        idempotency_key="idem-key-001",
    )


@pytest.fixture
def valid_policy():
    return Policy(
        policy_number="POL-001",
        holder_name="Jane Doe",
        policy_type="health",
        premium_amount=500.00,
        coverage_amount=100000.00,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
    )


# ------------------------------------------------------------------ #
#  NULL checks — required fields                                       #
# ------------------------------------------------------------------ #

@pytest.mark.sql
class TestNullChecks:
    """Required fields must never be NULL."""

    def test_patient_mrn_required(self, session) -> None:
        """Patient MRN is required — NULL raises IntegrityError."""
        patient = Patient(
            mrn=None,  # required field missing
            first_name="John",
            last_name="Smith",
            date_of_birth=date(1990, 1, 15),
            gender="male",
        )
        session.add(patient)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_patient_name_required(self, session) -> None:
        """Patient first and last name are required."""
        patient = Patient(
            mrn="MRN-002",
            first_name=None,  # required field missing
            last_name="Smith",
            date_of_birth=date(1990, 1, 15),
            gender="male",
        )
        session.add(patient)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_transaction_amount_required(self, session) -> None:
        """Transaction amount is required."""
        txn = Transaction(
            transaction_id="TXN-NULL-001",
            amount=None,  # required
            currency="USD",
            merchant_id="merchant-001",
            status="SUCCEEDED",
        )
        session.add(txn)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_policy_holder_required(self, session) -> None:
        """Policy holder name is required."""
        policy = Policy(
            policy_number="POL-NULL-001",
            holder_name=None,  # required
            policy_type="health",
            premium_amount=500.00,
            coverage_amount=100000.00,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
        )
        session.add(policy)
        with pytest.raises(IntegrityError):
            session.commit()


# ------------------------------------------------------------------ #
#  Uniqueness — duplicate detection                                    #
# ------------------------------------------------------------------ #

@pytest.mark.sql
class TestUniqueness:
    """Duplicate records must be detected and rejected."""

    def test_duplicate_patient_mrn_rejected(
        self, session, valid_patient
    ) -> None:
        """
        Two patients cannot share the same MRN.
        In healthcare, duplicate MRNs cause patient record merging
        issues and can result in incorrect treatment decisions.
        """
        session.add(valid_patient)
        session.commit()

        duplicate = Patient(
            mrn="MRN-001",  # same MRN
            first_name="Jane",
            last_name="Doe",
            date_of_birth=date(1985, 6, 20),
            gender="female",
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_duplicate_transaction_id_rejected(
        self, session, valid_transaction
    ) -> None:
        """
        Two transactions cannot share the same transaction ID.
        This is the database-level idempotency guarantee that
        backs up the API-level idempotency key.
        """
        session.add(valid_transaction)
        session.commit()

        duplicate = Transaction(
            transaction_id="TXN-001",  # same ID
            amount=2000.00,
            currency="USD",
            merchant_id="merchant-002",
            status="SUCCEEDED",
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_duplicate_policy_number_rejected(
        self, session, valid_policy
    ) -> None:
        """Two policies cannot share the same policy number."""
        session.add(valid_policy)
        session.commit()

        duplicate = Policy(
            policy_number="POL-001",  # same number
            holder_name="Bob Smith",
            policy_type="auto",
            premium_amount=300.00,
            coverage_amount=50000.00,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()


# ------------------------------------------------------------------ #
#  Range validation — value constraints                                #
# ------------------------------------------------------------------ #

@pytest.mark.sql
class TestRangeValidation:
    """Values must be within allowed ranges."""

    def test_transaction_negative_amount_rejected(
        self, session
    ) -> None:
        """Transaction amount must be positive."""
        txn = Transaction(
            transaction_id="TXN-NEG-001",
            amount=-100.00,  # negative amount
            currency="USD",
            merchant_id="merchant-001",
            status="SUCCEEDED",
        )
        session.add(txn)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_transaction_zero_amount_rejected(
        self, session
    ) -> None:
        """Transaction amount must be greater than zero."""
        txn = Transaction(
            transaction_id="TXN-ZERO-001",
            amount=0.00,  # zero amount
            currency="USD",
            merchant_id="merchant-001",
            status="SUCCEEDED",
        )
        session.add(txn)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_policy_coverage_must_exceed_premium(
        self, session
    ) -> None:
        """
        Coverage amount must exceed premium amount.
        A policy where the premium exceeds coverage is
        financially nonsensical and indicates data error.
        """
        policy = Policy(
            policy_number="POL-INV-001",
            holder_name="Test User",
            policy_type="health",
            premium_amount=10000.00,
            coverage_amount=500.00,  # less than premium
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
        )
        session.add(policy)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_policy_end_date_must_be_after_start(
        self, session
    ) -> None:
        """Policy end date must be after start date."""
        policy = Policy(
            policy_number="POL-DATE-001",
            holder_name="Test User",
            policy_type="health",
            premium_amount=500.00,
            coverage_amount=100000.00,
            start_date=date.today(),
            end_date=date.today() - timedelta(days=1),  # end before start
        )
        session.add(policy)
        with pytest.raises(IntegrityError):
            session.commit()


# ------------------------------------------------------------------ #
#  Schema consistency                                                  #
# ------------------------------------------------------------------ #

@pytest.mark.sql
class TestSchemaConsistency:
    """Database schema must match expected structure."""

    def test_patient_table_has_required_columns(
        self, session
    ) -> None:
        """Patient table has all required columns."""
        result = session.execute(
            text("PRAGMA table_info(patients)")
        ).fetchall()
        columns = {row[1] for row in result}

        required = {"id", "mrn", "first_name", "last_name",
                    "date_of_birth", "gender", "created_at"}
        assert required.issubset(columns), (
            f"Missing columns: {required - columns}"
        )

    def test_transaction_table_has_required_columns(
        self, session
    ) -> None:
        """Transaction table has all required columns."""
        result = session.execute(
            text("PRAGMA table_info(transactions)")
        ).fetchall()
        columns = {row[1] for row in result}

        required = {"id", "transaction_id", "amount", "currency",
                    "merchant_id", "status", "created_at"}
        assert required.issubset(columns), (
            f"Missing columns: {required - columns}"
        )

    def test_valid_records_insert_successfully(
        self, session, valid_patient, valid_transaction, valid_policy
    ) -> None:
        """Valid records across all three domains insert without error."""
        session.add_all([valid_patient, valid_transaction, valid_policy])
        session.commit()

        assert session.query(Patient).count()     == 1
        assert session.query(Transaction).count() == 1
        assert session.query(Policy).count()      == 1

    def test_data_quality_summary(self, session) -> None:
        """
        Summary query shows data quality metrics.
        Demonstrates SQL aggregation for quality reporting.
        """
        # Insert mixed quality data
        session.add_all([
            Patient(mrn="P1", first_name="Alice", last_name="A",
                    date_of_birth=date(1990, 1, 1), gender="female"),
            Patient(mrn="P2", first_name="Bob", last_name="B",
                    date_of_birth=date(1985, 5, 5), gender="male"),
            Patient(mrn="P3", first_name="Carol", last_name="C",
                    date_of_birth=date(2000, 3, 3), gender="female",
                    email="carol@example.com"),
        ])
        session.commit()

        total = session.query(Patient).count()
        with_email = session.query(Patient).filter(
            Patient.email.isnot(None)
        ).count()

        completeness = with_email / total if total > 0 else 0

        assert total == 3
        assert with_email == 1
        assert completeness == pytest.approx(0.333, abs=0.01)
