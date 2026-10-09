"""
Unit & Integration Tests for Safe Seeding in seed.py.
Verifies:
1. Ordinary seeding creates tables with create_all() and does NOT drop existing tables.
2. Pre-existing database data is preserved.
3. Ordinary seeding does NOT insert default users with hardcoded passwords or fallback secrets.
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import domain
from seed import seed


@pytest.fixture
def seed_test_db():
    """Isolated in-memory SQLite database for seeding verification."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


def test_seed_preserves_preexisting_data(seed_test_db):
    """Verify that calling seed() does NOT drop existing tables or delete existing custom records."""
    # 1. Create a custom pre-existing user and entity
    custom_user = domain.User(
        id="USR-CUSTOM-01",
        full_name="Preexisting Examiner",
        email="preexisting@ntro.gov",
        password_hash="pbkdf2_sha256$100000$test$testhash",
        organization="NTRO Technical Wing",
        role="REVIEWER",
        is_active=True,
    )
    seed_test_db.add(custom_user)
    seed_test_db.commit()

    # 2. Run seed
    seed(db_session=seed_test_db, reset_tables=False)

    # 3. Verify custom user still exists
    surviving_user = seed_test_db.query(domain.User).filter(domain.User.id == "USR-CUSTOM-01").first()
    assert surviving_user is not None
    assert surviving_user.email == "preexisting@ntro.gov"


def test_seed_does_not_create_default_hardcoded_privileged_users(seed_test_db):
    """Verify that ordinary seeding does NOT establish default accounts with hardcoded passwords."""
    seed(db_session=seed_test_db, reset_tables=False)

    # Verify no default supervisor or reviewer accounts were inserted by seed()
    sup = seed_test_db.query(domain.User).filter(domain.User.email == "supervisor@ntro.gov").first()
    assert sup is None

    rev = seed_test_db.query(domain.User).filter(domain.User.email == "reviewer@ntro.gov").first()
    assert rev is None

    # Entities and findings should be seeded
    entities = seed_test_db.query(domain.Entity).all()
    assert len(entities) == 10

    findings = seed_test_db.query(domain.Finding).all()
    assert len(findings) >= 1
