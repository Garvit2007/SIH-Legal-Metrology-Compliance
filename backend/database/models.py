from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    brand = Column(String(150))
    category = Column(String(100))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP, server_default=func.now())

    scans = relationship(
        "Scan",
        back_populates="product"
    )


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    scanned_by = Column(Integer, ForeignKey("users.id"))
    image_url = Column(Text, nullable=False)
    raw_ocr_text = Column(Text)
    extracted_data = Column(JSONB)
    status = Column(String(20), default="pending")
    created_at = Column(TIMESTAMP, server_default=func.now())

    product = relationship(
        "Product",
        back_populates="scans"
    )

    report = relationship(
        "ComplianceReport",
        back_populates="scan",
        uselist=False
    )


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id = Column(Integer, primary_key=True)
    scan_id = Column(
        Integer,
        ForeignKey("scans.id", ondelete="CASCADE")
    )
    overall_status = Column(String(20))
    compliance_score = Column(Numeric(5, 2))
    report_pdf_url = Column(Text)
    report_docx_url = Column(Text)
    generated_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )

    scan = relationship(
        "Scan",
        back_populates="report"
    )

    violations = relationship(
        "Violation",
        back_populates="report"
    )


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True)
    report_id = Column(
        Integer,
        ForeignKey(
            "compliance_reports.id",
            ondelete="CASCADE"
        )
    )
    field_name = Column(String(100))
    rule_citation = Column(String(255))
    severity = Column(String(20))
    message = Column(Text)
    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )

    report = relationship(
        "ComplianceReport",
        back_populates="violations"
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100))
    details = Column(JSONB)
    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )
