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
    refund_window_days: int = 30

    # Fault injection for the Beat 8 crash test. Zero in every real run.
    refund_activity_delay_seconds: float = 0.0

    # Fault injection. When true the fake payment processor rejects every
    # refund, so the compensation path can be exercised.
    processor_rejects: bool = False


settings = Settings()
