from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Visitor Management System"
    app_env: str = "development"
    app_release_version: str = "1.0.0-rc1"
    frontend_port: int = 7272
    backend_port: int = 7273
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'vms-local.db'}"

    def resolved_database_url(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:///./"):
            relative_path = url.replace("sqlite:///./", "")
            absolute = PROJECT_ROOT / relative_path
            absolute.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{absolute}"
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            path_part = url.replace("sqlite:///", "")
            if not path_part.startswith("/"):
                absolute = PROJECT_ROOT / path_part
                absolute.parent.mkdir(parents=True, exist_ok=True)
                return f"sqlite:///{absolute}"
        return url
    dev_auth_enabled: bool = False
    dev_auth_email: str = "sheru.bohra@lazypay.in"
    dev_auth_user: Optional[str] = None  # DEV_AUTH_USER env alias supported via model config
    auth_mode: str = "dev"  # dev | vms_native | entra
    entra_auth_enabled: bool = False
    vms_native_auth_enabled: bool = True
    global_admin_initial_password: Optional[str] = None
    vms_native_session_ttl_minutes: int = 480
    vms_native_max_failed_attempts: int = 5
    vms_native_lockout_minutes: int = 15
    direct_owner_auth_enabled: bool = False  # legacy alias for vms_native_auth_enabled
    direct_owner_session_ttl_minutes: int = 480
    direct_owner_max_failed_attempts: int = 5
    direct_owner_lockout_minutes: int = 15
    cors_origins: str = "http://localhost:7272"
    cors_allowed_origins: Optional[str] = None  # alias; falls back to cors_origins

    audit_integrity_key: Optional[str] = None
    audit_integrity_version: int = 1

    document_encryption_key: Optional[str] = None
    document_encryption_version: int = 1

    rate_limit_backend: str = "memory"  # memory | database

    file_scanner_provider: str = "dev_noop"  # dev_noop | clamav
    clamav_host: Optional[str] = None
    clamav_port: int = 3310
    clamav_timeout_seconds: int = 15

    retention_automation_enabled: bool = False

    access_control_enabled: bool = False
    access_control_provider: str = "disabled"
    access_control_required_for_readiness: bool = False
    access_provider_timeout_seconds: int = 15
    access_provider_max_attempts: int = 5
    access_provider_retry_base_seconds: int = 30
    access_mock_simulate_unavailable: bool = False
    access_mock_simulate_failure: bool = False

    badge_printer_enabled: bool = False
    badge_printer_provider: str = "disabled"
    badge_printer_required_for_readiness: bool = False
    badge_printer_timeout_seconds: int = 15
    badge_print_max_attempts: int = 3
    badge_printer_mock_simulate_offline: bool = False

    physical_integration_scheduler_enabled: bool = True

    production_database_dialect: str = "postgresql"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    db_connect_timeout_seconds: int = 10
    db_sslmode: Optional[str] = None
    db_statement_timeout_ms: int = 30000
    db_application_name: str = "vms"
    db_sql_echo: bool = False
    schema_check_on_startup: bool = False
    app_shutdown_timeout_seconds: int = 30

    log_format: str = "text"
    log_level: str = "INFO"

    notification_backlog_attention: int = 100
    notification_backlog_critical: int = 500
    physical_queue_attention: int = 50
    physical_queue_critical: int = 200

    test_postgres_url: Optional[str] = None
    allow_postgres_test_database: bool = False

    enable_live_integration_tests: bool = False
    email_live_test_recipient: Optional[str] = None
    live_email_allowed_recipients: Optional[str] = None

    entra_allowed_client_ids: Optional[str] = None

    entra_tenant_id: Optional[str] = None
    entra_client_id: Optional[str] = None
    entra_client_secret: Optional[str] = None
    entra_redirect_uri: Optional[str] = None
    entra_post_logout_redirect_uri: Optional[str] = None
    entra_api_audience: Optional[str] = None  # legacy API resource audience (optional)
    entra_required_scope: Optional[str] = None  # deprecated — OIDC uses openid/profile/email
    entra_clock_skew_seconds: int = 120
    vms_bootstrap_admin_email: Optional[str] = None

    vms_data_encryption_key: Optional[str] = None

    graph_tenant_id: Optional[str] = None
    graph_client_id: Optional[str] = None
    graph_client_secret: Optional[str] = None
    graph_sender_mailbox: Optional[str] = None
    graph_timeout_seconds: int = 15
    graph_save_to_sent_items: bool = True

    invitation_early_arrival_minutes: int = 120
    invitation_late_grace_minutes: int = 120

    host_approval_token_ttl_hours: int = 24
    upcoming_visit_reminder_minutes: int = 60
    public_app_base_url: str = "http://localhost:7272"

    notification_max_attempts: int = 3
    background_scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 60
    host_approval_resend_cooldown_minutes: int = 5

    name_strong_match_threshold: int = 85
    name_possible_match_threshold: int = 70
    duplicate_visit_window_minutes: int = 120
    repeated_invalid_scan_window_minutes: int = 60
    security_screening_version: str = "v1"

    compliance_document_max_mb: int = 10
    compliance_upload_subdir: str = "vendor-compliance"
    vms_local_media_root: str = "./data/visitor-media"
    visitor_photo_max_mb: int = 5
    safety_policy_version: str = "1.0"

    report_export_max_rows: int = 10000
    analytics_max_range_days: int = 366

    rate_limit_public_per_minute: int = 60
    rate_limit_registration_per_minute: int = 10
    rate_limit_invitation_per_minute: int = 30
    rate_limit_host_approval_per_minute: int = 30
    rate_limit_ai_copilot_per_minute: int = 20
    rate_limit_ai_insight_refresh_per_minute: int = 5
    rate_limit_direct_owner_login_per_minute: int = 10
    rate_limit_vms_native_login_per_minute: int = 10
    rate_limit_vms_native_password_change_per_minute: int = 10
    trust_proxy_headers: bool = False

    @property
    def resolved_vms_native_auth_enabled(self) -> bool:
        if self.auth_mode == "vms_native":
            return True
        if self.auth_mode == "entra":
            return self.vms_native_auth_enabled or self.direct_owner_auth_enabled
        return False

    @property
    def resolved_vms_native_session_ttl_minutes(self) -> int:
        return self.vms_native_session_ttl_minutes or self.direct_owner_session_ttl_minutes

    @property
    def resolved_vms_native_max_failed_attempts(self) -> int:
        return self.vms_native_max_failed_attempts or self.direct_owner_max_failed_attempts

    @property
    def resolved_vms_native_lockout_minutes(self) -> int:
        return self.vms_native_lockout_minutes or self.direct_owner_lockout_minutes

    ai_enabled: bool = True
    ai_provider: str = "dev_mock"
    ai_max_context_records: int = 100
    ai_max_query_length: int = 1000
    ai_interaction_retention_days: int = 30
    ai_provider_timeout_seconds: int = 15
    intelligence_scheduler_interval_seconds: int = 300
    ai_overstay_attention_minutes: int = 30
    ai_overstay_urgent_minutes: int = 120
    ai_approval_delay_minutes: int = 30
    ai_security_review_aging_minutes: int = 30

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_allowed_origins or self.cors_origins
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def entra_allowed_client_id_list(self) -> list[str]:
        if not self.entra_allowed_client_ids:
            return []
        return [c.strip() for c in self.entra_allowed_client_ids.split(",") if c.strip()]

    @property
    def live_email_allowed_recipient_list(self) -> list[str]:
        if self.live_email_allowed_recipients:
            return [e.strip().lower() for e in self.live_email_allowed_recipients.split(",") if e.strip()]
        if self.email_live_test_recipient:
            return [self.email_live_test_recipient.strip().lower()]
        return []

    def validate_live_email_recipient(self, recipient: str) -> bool:
        allowed = self.live_email_allowed_recipient_list
        if not allowed:
            return False
        return recipient.strip().lower() in allowed

    def validate_environment(self) -> None:
        from app.core.secret_validation import is_weak_secret, validate_production_secret

        if self.is_production and self.dev_auth_enabled:
            raise RuntimeError(
                "DEV_AUTH_ENABLED cannot be true when APP_ENV=production. "
                "Refusing to start with insecure dev authentication."
            )
        if self.is_production and self.auth_mode not in ("vms_native", "entra"):
            raise RuntimeError("AUTH_MODE must be 'vms_native' or 'entra' when APP_ENV=production.")
        if self.is_production and self.auth_mode != "vms_native":
            raise RuntimeError("AUTH_MODE must be 'vms_native' when APP_ENV=production.")
        if self.is_production and self.email_provider == "dev_outbox":
            raise RuntimeError(
                "EMAIL_PROVIDER=dev_outbox cannot be used when APP_ENV=production."
            )
        if self.is_production and self.ai_provider == "dev_mock" and self.ai_enabled:
            raise RuntimeError(
                "AI_PROVIDER=dev_mock cannot be enabled when APP_ENV=production."
            )
        if self.is_production:
            if self.entra_auth_enabled and (not self.entra_tenant_id or not self.entra_client_id):
                raise RuntimeError(
                    "ENTRA_TENANT_ID and ENTRA_CLIENT_ID are required when ENTRA_AUTH_ENABLED=true in production."
                )
            if self.email_provider == "ms_graph":
                raise RuntimeError(
                    "EMAIL_PROVIDER=ms_graph is not supported. Microsoft Graph is not used by VMS."
                )
            if self.public_app_base_url and not self.public_app_base_url.startswith("https://"):
                raise RuntimeError("PUBLIC_APP_BASE_URL must use HTTPS in production.")
            validate_production_secret("AUDIT_INTEGRITY_KEY", self.audit_integrity_key)
            validate_production_secret("VMS_DATA_ENCRYPTION_KEY", self.vms_data_encryption_key)
            validate_production_secret("DOCUMENT_ENCRYPTION_KEY", self.document_encryption_key)
            if self.rate_limit_backend != "database":
                raise RuntimeError("RATE_LIMIT_BACKEND must be 'database' in production.")
            if self.file_scanner_provider == "dev_noop":
                raise RuntimeError("FILE_SCANNER_PROVIDER=dev_noop cannot be used in production.")
            if "*" in self.cors_origin_list:
                raise RuntimeError("Wildcard CORS origin is not allowed in production.")
            if self.access_control_enabled and self.access_control_provider == "dev_mock":
                raise RuntimeError("ACCESS_CONTROL_PROVIDER=dev_mock cannot be used when ACCESS_CONTROL_ENABLED=true in production.")
            if self.badge_printer_enabled and self.badge_printer_provider == "dev_mock":
                raise RuntimeError("BADGE_PRINTER_PROVIDER=dev_mock cannot be used when BADGE_PRINTER_ENABLED=true in production.")
            if self.db_sql_echo:
                raise RuntimeError("DB_SQL_ECHO must be false in production.")
            url = self.resolved_database_url()
            if url.startswith("sqlite"):
                raise RuntimeError("SQLite DATABASE_URL cannot be used when APP_ENV=production.")
            if not self.resolved_vms_native_auth_enabled:
                raise RuntimeError(
                    "VMS native authentication must be enabled when APP_ENV=production."
                )

    email_provider: str = "dev_outbox"

    @property
    def public_app_origin(self) -> str:
        return self.public_app_base_url.rstrip("/")

    @property
    def compliance_upload_root(self) -> Path:
        root = PROJECT_ROOT / "data" / "uploads" / self.compliance_upload_subdir
        root.mkdir(parents=True, exist_ok=True)
        return root

    @property
    def resolved_local_media_root(self) -> Path:
        raw = (self.vms_local_media_root or "./data/visitor-media").strip()
        if raw.startswith("./"):
            path = PROJECT_ROOT / raw[2:]
        elif not Path(raw).is_absolute():
            path = PROJECT_ROOT / raw
        else:
            path = Path(raw)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
