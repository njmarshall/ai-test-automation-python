"""
sql_models.py
-------------
SQLAlchemy models for the SQL data quality sandbox.

Real-world context
------------------
At Indeed, SQL data quality was critical for job search
relevance. Missing fields, duplicates, and range violations
caused silent ranking failures that were hard to debug.

At Finix, duplicate transaction records caused reconciliation
failures and compliance issues.

At healthcare companies, NULL required fields in patient
records could cause downstream FHIR validation failures.

These models represent three domains:
- Patient (healthcare FHIR context)
- Transaction (fintech/payments context)
- Policy (insurance context)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime,
    Float, Integer, String, Text, UniqueConstraint,
    create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session


# ------------------------------------------------------------------ #
#  Base                                                                #
# ------------------------------------------------------------------ #

class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------ #
#  Healthcare — Patient table                                          #
# ------------------------------------------------------------------ #

class Patient(Base):
    """
    FHIR-inspired patient table.

    Required fields (NOT NULL):
    - mrn: medical record number
    - last_name, first_name
    - date_of_birth
    - gender

    Data quality rules:
    - No duplicate MRNs
    - Gender must be in allowed values
    - Date of birth cannot be in future
    """
    __tablename__ = "patients"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    mrn           = Column(String(50),  nullable=False, unique=True)
    first_name    = Column(String(100), nullable=False)
    last_name     = Column(String(100), nullable=False)
    date_of_birth = Column(Date,        nullable=False)
    gender        = Column(String(20),  nullable=False)
    email         = Column(String(200), nullable=True)
    phone         = Column(String(20),  nullable=True)
    created_at    = Column(DateTime,    nullable=False,
                          default=datetime.utcnow)
    is_active     = Column(Boolean,     nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "gender IN ('male', 'female', 'other', 'unknown')",
            name="ck_patient_gender"
        ),
    )


# ------------------------------------------------------------------ #
#  Fintech — Transaction table                                         #
# ------------------------------------------------------------------ #

class Transaction(Base):
    """
    Payment transaction table.

    Required fields (NOT NULL):
    - transaction_id: unique identifier
    - amount: must be positive
    - currency: ISO 4217
    - merchant_id
    - status

    Data quality rules:
    - No duplicate transaction_ids
    - Amount must be > 0
    - Currency must be valid ISO code
    - Status must be in allowed values
    """
    __tablename__ = "transactions"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    transaction_id = Column(String(100), nullable=False, unique=True)
    amount         = Column(Float,       nullable=False)
    currency       = Column(String(3),   nullable=False)
    merchant_id    = Column(String(100), nullable=False)
    status         = Column(String(20),  nullable=False)
    idempotency_key= Column(String(255), nullable=True)
    created_at     = Column(DateTime,    nullable=False,
                           default=datetime.utcnow)
    description    = Column(Text,        nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transaction_amount_positive"),
        CheckConstraint(
            "status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'REFUNDED')",
            name="ck_transaction_status"
        ),
        CheckConstraint(
            "length(currency) = 3",
            name="ck_transaction_currency_length"
        ),
    )


# ------------------------------------------------------------------ #
#  Insurance — Policy table                                            #
# ------------------------------------------------------------------ #

class Policy(Base):
    """
    Insurance policy table.

    Required fields (NOT NULL):
    - policy_number: unique identifier
    - holder_name
    - premium_amount: must be > 0
    - coverage_amount: must be > 0
    - start_date, end_date

    Data quality rules:
    - No duplicate policy numbers
    - End date must be after start date
    - Coverage amount must exceed premium amount
    - Policy type must be valid
    """
    __tablename__ = "policies"

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    policy_number   = Column(String(50),  nullable=False, unique=True)
    holder_name     = Column(String(200), nullable=False)
    policy_type     = Column(String(50),  nullable=False)
    premium_amount  = Column(Float,       nullable=False)
    coverage_amount = Column(Float,       nullable=False)
    start_date      = Column(Date,        nullable=False)
    end_date        = Column(Date,        nullable=False)
    is_active       = Column(Boolean,     nullable=False, default=True)
    created_at      = Column(DateTime,    nullable=False,
                            default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "premium_amount > 0",
            name="ck_policy_premium_positive"
        ),
        CheckConstraint(
            "coverage_amount > 0",
            name="ck_policy_coverage_positive"
        ),
        CheckConstraint(
            "coverage_amount > premium_amount",
            name="ck_policy_coverage_exceeds_premium"
        ),
        CheckConstraint(
            "end_date > start_date",
            name="ck_policy_date_range"
        ),
        CheckConstraint(
            "policy_type IN ('health', 'auto', 'life', 'property')",
            name="ck_policy_type"
        ),
    )


# ------------------------------------------------------------------ #
#  Sandbox factory                                                     #
# ------------------------------------------------------------------ #

def create_sandbox_engine(db_url: str = "sqlite:///:memory:"):
    """
    Create an in-memory SQLite engine for testing.

    SQLite in-memory is perfect for data quality tests:
    - Fast (no disk I/O)
    - Isolated (each test gets a fresh database)
    - No cleanup required

    For production, replace with PostgreSQL or MySQL URL.
    """
    engine = create_engine(db_url, echo=False)

    # Enable foreign key enforcement for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def create_sandbox_session(engine=None) -> Session:
    """Create a SQLAlchemy session for the sandbox."""
    if engine is None:
        engine = create_sandbox_engine()
    return Session(engine)
