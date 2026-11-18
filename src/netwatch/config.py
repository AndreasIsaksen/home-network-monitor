from __future__ import annotations

import os
from dataclasses import dataclass


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str
    timezone: str
    schedule: str
    run_on_start: bool
    router_targets: tuple[str, ...]
    dns_candidates: tuple[str, ...]
    router_ping_count: int
    dns_selection_ping_count: int
    dns_ping_count: int
    ping_interval_seconds: float
    speedtest_server_id: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        return cls(
            database_url=database_url,
            timezone=os.getenv("TZ", "Etc/UTC"),
            schedule=os.getenv("SCHEDULE", "0 */6 * * *"),
            run_on_start=_boolean("RUN_ON_START", True),
            router_targets=_csv("ROUTER_TARGETS", "auto"),
            dns_candidates=_csv("DNS_CANDIDATES", "9.9.9.9,1.1.1.1,8.8.8.8"),
            router_ping_count=int(os.getenv("ROUTER_PING_COUNT", "100")),
            dns_selection_ping_count=int(os.getenv("DNS_SELECTION_PING_COUNT", "20")),
            dns_ping_count=int(os.getenv("DNS_PING_COUNT", "100")),
            ping_interval_seconds=float(os.getenv("PING_INTERVAL_SECONDS", "0.2")),
            speedtest_server_id=os.getenv("SPEEDTEST_SERVER_ID") or None,
        )
