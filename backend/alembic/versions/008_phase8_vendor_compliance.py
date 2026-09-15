"""Phase 8: vendor compliance

Revision ID: 008
Revises: 007
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _visit_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("visits")}


def _vt_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("visitor_types")}


def upgrade() -> None:
    bind = op.get_bind()
    vt_cols = _vt_columns(bind)
    if "requires_vendor_compliance" not in vt_cols:
        op.add_column(
            "visitor_types",
            sa.Column("requires_vendor_compliance", sa.Boolean(), nullable=False, server_default="0"),
        )
    if "po_reference_required" not in vt_cols:
        op.add_column(
            "visitor_types",
            sa.Column("po_reference_required", sa.Boolean(), nullable=False, server_default="0"),
        )

    visit_cols = _visit_columns(bind)
    if "compliance_status" not in visit_cols:
        op.add_column(
            "visits",
            sa.Column("compliance_status", sa.String(length=30), nullable=False, server_default="COMPLIANT"),
        )
        op.create_index(op.f("ix_visits_compliance_status"), "visits", ["compliance_status"], unique=False)

    if not _table_exists(bind, "vendor_companies"):
        op.create_table(
            "vendor_companies",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("normalized_name", sa.String(length=255), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=True),
            sa.Column("primary_contact_name", sa.String(length=255), nullable=True),
            sa.Column("primary_contact_email", sa.String(length=255), nullable=True),
            sa.Column("primary_contact_mobile", sa.String(length=50), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["admin_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_vendor_companies_normalized_name"), "vendor_companies", ["normalized_name"], unique=False)

    if not _table_exists(bind, "vendor_company_locations"):
        op.create_table(
            "vendor_company_locations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("vendor_company_id", sa.Integer(), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["vendor_company_id"], ["vendor_companies.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_vendor_company_locations_vendor_company_id"), "vendor_company_locations", ["vendor_company_id"], unique=False)
        op.create_index(op.f("ix_vendor_company_locations_location_id"), "vendor_company_locations", ["location_id"], unique=False)

    if not _table_exists(bind, "vendor_visitor_profiles"):
        op.create_table(
            "vendor_visitor_profiles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("visitor_id", sa.Integer(), nullable=False),
            sa.Column("vendor_company_id", sa.Integer(), nullable=False),
            sa.Column("employee_reference", sa.String(length=100), nullable=True),
            sa.Column("trade_or_role", sa.String(length=255), nullable=True),
            sa.Column("supervisor_name", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["vendor_company_id"], ["vendor_companies.id"]),
            sa.ForeignKeyConstraint(["visitor_id"], ["visitors.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_vendor_visitor_profiles_visitor_id"), "vendor_visitor_profiles", ["visitor_id"], unique=False)
        op.create_index(op.f("ix_vendor_visitor_profiles_vendor_company_id"), "vendor_visitor_profiles", ["vendor_company_id"], unique=False)

    if not _table_exists(bind, "vendor_visit_details"):
        op.create_table(
            "vendor_visit_details",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("visit_id", sa.Integer(), nullable=False),
            sa.Column("vendor_company_id", sa.Integer(), nullable=False),
            sa.Column("work_purpose", sa.Text(), nullable=True),
            sa.Column("po_work_order_reference", sa.String(length=100), nullable=True),
            sa.Column("work_area", sa.String(length=255), nullable=True),
            sa.Column("vendor_supervisor", sa.String(length=255), nullable=True),
            sa.Column("company_contact_host_id", sa.Integer(), nullable=True),
            sa.Column("safety_acknowledged", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("safety_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("safety_policy_version", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["company_contact_host_id"], ["hosts.id"]),
            sa.ForeignKeyConstraint(["vendor_company_id"], ["vendor_companies.id"]),
            sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("visit_id"),
        )
        op.create_index(op.f("ix_vendor_visit_details_visit_id"), "vendor_visit_details", ["visit_id"], unique=False)
        op.create_index(op.f("ix_vendor_visit_details_vendor_company_id"), "vendor_visit_details", ["vendor_company_id"], unique=False)

    if not _table_exists(bind, "compliance_requirements"):
        op.create_table(
            "compliance_requirements",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("visitor_type_id", sa.Integer(), nullable=True),
            sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="GLOBAL"),
            sa.Column("location_id", sa.Integer(), nullable=True),
            sa.Column("document_owner_type", sa.String(length=20), nullable=False, server_default="VISITOR"),
            sa.Column("document_required", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("validity_required", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("safety_acknowledgement_required", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("expiry_warning_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["visitor_type_id"], ["visitor_types.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index(op.f("ix_compliance_requirements_visitor_type_id"), "compliance_requirements", ["visitor_type_id"], unique=False)
        op.create_index(op.f("ix_compliance_requirements_location_id"), "compliance_requirements", ["location_id"], unique=False)

    if not _table_exists(bind, "compliance_documents"):
        op.create_table(
            "compliance_documents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("requirement_id", sa.Integer(), nullable=False),
            sa.Column("visitor_id", sa.Integer(), nullable=True),
            sa.Column("vendor_company_id", sa.Integer(), nullable=True),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("storage_key", sa.String(length=255), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("uploaded_by_actor_type", sa.String(length=20), nullable=False, server_default="ADMIN_USER"),
            sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING_VERIFICATION"),
            sa.Column("scan_status", sa.String(length=30), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
            sa.Column("rejection_comment", sa.Text(), nullable=True),
            sa.Column("supersedes_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["requirement_id"], ["compliance_requirements.id"]),
            sa.ForeignKeyConstraint(["supersedes_id"], ["compliance_documents.id"]),
            sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["verified_by_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["vendor_company_id"], ["vendor_companies.id"]),
            sa.ForeignKeyConstraint(["visitor_id"], ["visitors.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_compliance_documents_requirement_id"), "compliance_documents", ["requirement_id"], unique=False)
        op.create_index(op.f("ix_compliance_documents_visitor_id"), "compliance_documents", ["visitor_id"], unique=False)
        op.create_index(op.f("ix_compliance_documents_vendor_company_id"), "compliance_documents", ["vendor_company_id"], unique=False)
        op.create_index(op.f("ix_compliance_documents_valid_until"), "compliance_documents", ["valid_until"], unique=False)
        op.create_index(op.f("ix_compliance_documents_status"), "compliance_documents", ["status"], unique=False)

    if not _table_exists(bind, "compliance_evaluations"):
        op.create_table(
            "compliance_evaluations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("visit_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("evaluation_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reason_summary", sa.Text(), nullable=True),
            sa.Column("signals_json", sa.Text(), nullable=True),
            sa.Column("trigger", sa.String(length=50), nullable=True),
            sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_compliance_evaluations_visit_id"), "compliance_evaluations", ["visit_id"], unique=False)
        op.create_index(op.f("ix_compliance_evaluations_status"), "compliance_evaluations", ["status"], unique=False)
        op.create_index(op.f("ix_compliance_evaluations_evaluated_at"), "compliance_evaluations", ["evaluated_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "compliance_evaluations",
        "compliance_documents",
        "compliance_requirements",
        "vendor_visit_details",
        "vendor_visitor_profiles",
        "vendor_company_locations",
        "vendor_companies",
    ):
        if _table_exists(bind, table):
            op.drop_table(table)
    visit_cols = _visit_columns(bind)
    if "compliance_status" in visit_cols:
        op.drop_index(op.f("ix_visits_compliance_status"), table_name="visits")
        op.drop_column("visits", "compliance_status")
    vt_cols = _vt_columns(bind)
    if "po_reference_required" in vt_cols:
        op.drop_column("visitor_types", "po_reference_required")
    if "requires_vendor_compliance" in vt_cols:
        op.drop_column("visitor_types", "requires_vendor_compliance")
