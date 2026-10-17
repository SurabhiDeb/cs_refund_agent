"""Typed settings, read once from the environment.

The refund cap and the kill switch live here, not in a prompt.
A prompt is advice.
A value checked in code is a rule.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6380/0"
    temporal_address: str = "localhost:7233"
    # Route refunds through the Temporal workflow instead of writing them
    # in this process. Off in tests and evals, on wherever a crash between
    # deciding and writing would cost real money.
    durable_refunds: bool = False

    # The pool is the service's real concurrency limit, not the CPU. Beat
    # 13.1 found SQLAlchemy's defaults, 5 connections plus 10 overflow,
    # queueing at 20 concurrent callers on two workers.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    # Fail fast. A caller that cannot get a connection in five seconds
    # should be told so, not held for thirty.
    db_pool_timeout_seconds: int = 5

    llm_base_url: str
    llm_api_key: str
    llm_model: str

    # From the gateway's /models endpoint. Pinned, not
    # fetched, so a run's recorded cost is reproducible. Re-check these when
    # you change model.
    llm_input_inr_per_million: float = 10.2
    llm_output_inr_per_million: float = 50.8

    # A refund at or below this may be issued by the agent.
    # Above it, escalates.
    refund_cap_minor_units: int = 5000

    # The kill switch. False means every write tool refuses,
    # and the agent degrades to read plus escalate.
    write_tools_enabled: bool = False

    # Serve a canned model instead of calling the gateway. For load tests
    # only: k6 at any useful concurrency against the real model costs more
    # than every evaluation in this project put together.
    fake_model: bool = False

    refund_window_days: int = 30

    # Per key, per window. Low on purpose. Every call spends gateway credits.
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60

    # Tracing. Empty host means tracing is off, which is how CI runs.
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # Empty DSN means Sentry is off, which is how CI and tests run.
    sentry_dsn: str = ""
    sentry_environment: str = "local"

    # Fault injection for the Beat 8 crash test. Zero in every real run.
    refund_activity_delay_seconds: float = 0.0

    # Fault injection. When true the fake payment processor rejects every
    # refund, so the compensation path can be exercised.
    processor_rejects: bool = False


settings = Settings()
