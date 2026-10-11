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

    # A refund at or below this may be issued by the agent.
    # Above it, escalates.
    refund_cap_minor_units: int = 5000

    # The kill switch. False means every write tool refuses,
    # and the agent degrades to read plus escalate.
    write_tools_enabled: bool = False
    refund_window_days: int = 30


settings = Settings()
