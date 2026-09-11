import pytest
import uuid

from db import SessionLocal
from models import User, Product, Scan, ComplianceReport, Violation


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def test_create_user(db):
    email = f"officer1-test-{uuid.uuid4()}@example.com"

    user = User(
        name="Officer2",
        email=email,
        password_hash="hash",
        role="admin"
    )

    db.add(user)
    db.commit()

    assert user.id is not None

    db.delete(user)
    db.commit()


def test_create_product_and_scan(db):
    email = f"officer2-test-{uuid.uuid4()}@example.com"

    user = User(
        name="Officer2",
        email=email,
        password_hash="hash",
        role="admin"
    )

    db.add(user)
    db.commit()

    product = Product(
        name="Sample Biscuit",
        brand="TestBrand",
        created_by=user.id
    )

    db.add(product)
    db.commit()

    scan = Scan(
        product_id=product.id,
        scanned_by=user.id,
        image_url="http://example.com/img.jpg",
        status="pending"
    )

    db.add(scan)
    db.commit()

    assert scan.id is not None

    # Delete in dependency order
    db.delete(scan)
    db.commit()

    db.delete(product)
    db.commit()

    db.delete(user)
    db.commit()