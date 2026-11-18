from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path
from typing import Any, TextIO

import psycopg
from psycopg.types.json import Jsonb


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS network_test_runs (
    id BIGSERIAL PRIMARY KEY,
    measured_at TIMESTAMPTZ NOT NULL,
    interface_name TEXT NOT NULL,
    link_speed_mbps INTEGER,
    duplex TEXT,
    wifi_signal_dbm DOUBLE PRECISION,
    wifi_tx_bitrate_mbps DOUBLE PRECISION,
    wifi_rx_bitrate_mbps DOUBLE PRECISION,
    default_gateway INET NOT NULL,
    router_results JSONB NOT NULL,
    dns_target INET NOT NULL,
    dns_result JSONB NOT NULL,
    dns_candidates JSONB NOT NULL,
    download_mbps DOUBLE PRECISION,
    upload_mbps DOUBLE PRECISION,
    idle_latency_ms DOUBLE PRECISION,
    idle_jitter_ms DOUBLE PRECISION,
    loaded_download_latency_ms DOUBLE PRECISION,
    loaded_upload_latency_ms DOUBLE PRECISION,
    speedtest_packet_loss_pct DOUBLE PRECISION,
    isp TEXT,
    external_ip INET,
    server_id INTEGER,
    server_name TEXT,
    server_location TEXT,
    server_country TEXT,
    result_url TEXT,
    rx_errors_delta BIGINT,
    rx_dropped_delta BIGINT,
    rx_missed_errors_delta BIGINT,
    tx_errors_delta BIGINT,
    tx_dropped_delta BIGINT,
    collisions_delta BIGINT,
    raw_speedtest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS network_test_runs_measured_at_idx
    ON network_test_runs (measured_at DESC);
ALTER TABLE network_test_runs ADD COLUMN IF NOT EXISTS wifi_signal_dbm DOUBLE PRECISION;
ALTER TABLE network_test_runs ADD COLUMN IF NOT EXISTS wifi_tx_bitrate_mbps DOUBLE PRECISION;
ALTER TABLE network_test_runs ADD COLUMN IF NOT EXISTS wifi_rx_bitrate_mbps DOUBLE PRECISION;
"""

BASE_HEADERS = [
    "measured_at", "interface_name", "link_speed_mbps", "duplex", "wifi_signal_dbm",
    "wifi_tx_bitrate_mbps", "wifi_rx_bitrate_mbps", "default_gateway",
    "router_target", "router_packet_loss_pct", "router_latency_min_ms", "router_latency_avg_ms",
    "router_latency_max_ms", "router_jitter_ms", "additional_router_results",
    "dns_target", "dns_packet_loss_pct", "dns_latency_min_ms", "dns_latency_avg_ms",
    "dns_latency_max_ms", "dns_jitter_ms", "dns_candidate_results",
    "download_mbps", "upload_mbps", "idle_latency_ms", "idle_jitter_ms",
    "loaded_download_latency_ms", "loaded_upload_latency_ms", "speedtest_packet_loss_pct",
    "isp", "external_ip", "speedtest_server_id", "speedtest_server_name",
    "speedtest_server_location", "speedtest_server_country", "result_url",
    "rx_errors_delta", "rx_dropped_delta", "rx_missed_errors_delta", "tx_errors_delta",
    "tx_dropped_delta", "collisions_delta",
]


def connect_with_retry(database_url: str, attempts: int = 30) -> psycopg.Connection:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return psycopg.connect(database_url)
        except psycopg.OperationalError as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError("PostgreSQL did not become ready") from last_error


def initialize(database_url: str) -> None:
    with connect_with_retry(database_url) as connection:
        connection.execute(SCHEMA_SQL)


def insert_result(database_url: str, result: dict[str, Any]) -> int:
    columns = [
        "measured_at", "interface_name", "link_speed_mbps", "duplex", "wifi_signal_dbm",
        "wifi_tx_bitrate_mbps", "wifi_rx_bitrate_mbps", "default_gateway",
        "router_results", "dns_target", "dns_result", "dns_candidates", "download_mbps",
        "upload_mbps", "idle_latency_ms", "idle_jitter_ms", "loaded_download_latency_ms",
        "loaded_upload_latency_ms", "speedtest_packet_loss_pct", "isp", "external_ip",
        "server_id", "server_name", "server_location", "server_country", "result_url",
        "rx_errors_delta", "rx_dropped_delta", "rx_missed_errors_delta", "tx_errors_delta",
        "tx_dropped_delta", "collisions_delta", "raw_speedtest",
    ]
    json_columns = {"router_results", "dns_result", "dns_candidates", "raw_speedtest"}
    values = [Jsonb(result[name]) if name in json_columns else result.get(name) for name in columns]
    placeholders = ", ".join(["%s"] * len(columns))
    query = f"INSERT INTO network_test_runs ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id"
    with connect_with_retry(database_url) as connection:
        return connection.execute(query, values).fetchone()[0]


def _csv_row(row: dict[str, Any]) -> dict[str, Any]:
    routers = row["router_results"] or []
    router = routers[0] if routers else {}
    dns = row["dns_result"] or {}
    return {
        "measured_at": row["measured_at"].isoformat(),
        "interface_name": row["interface_name"],
        "link_speed_mbps": row["link_speed_mbps"],
        "duplex": row["duplex"],
        "wifi_signal_dbm": row["wifi_signal_dbm"],
        "wifi_tx_bitrate_mbps": row["wifi_tx_bitrate_mbps"],
        "wifi_rx_bitrate_mbps": row["wifi_rx_bitrate_mbps"],
        "default_gateway": str(row["default_gateway"]),
        "router_target": router.get("target"),
        "router_packet_loss_pct": router.get("packet_loss_pct"),
        "router_latency_min_ms": router.get("latency_min_ms"),
        "router_latency_avg_ms": router.get("latency_avg_ms"),
        "router_latency_max_ms": router.get("latency_max_ms"),
        "router_jitter_ms": router.get("jitter_ms"),
        "additional_router_results": json.dumps(routers[1:], separators=(",", ":")),
        "dns_target": str(row["dns_target"]),
        "dns_packet_loss_pct": dns.get("packet_loss_pct"),
        "dns_latency_min_ms": dns.get("latency_min_ms"),
        "dns_latency_avg_ms": dns.get("latency_avg_ms"),
        "dns_latency_max_ms": dns.get("latency_max_ms"),
        "dns_jitter_ms": dns.get("jitter_ms"),
        "dns_candidate_results": json.dumps(row["dns_candidates"], separators=(",", ":")),
        "download_mbps": row["download_mbps"],
        "upload_mbps": row["upload_mbps"],
        "idle_latency_ms": row["idle_latency_ms"],
        "idle_jitter_ms": row["idle_jitter_ms"],
        "loaded_download_latency_ms": row["loaded_download_latency_ms"],
        "loaded_upload_latency_ms": row["loaded_upload_latency_ms"],
        "speedtest_packet_loss_pct": row["speedtest_packet_loss_pct"],
        "isp": row["isp"],
        "external_ip": str(row["external_ip"]) if row["external_ip"] else None,
        "speedtest_server_id": row["server_id"],
        "speedtest_server_name": row["server_name"],
        "speedtest_server_location": row["server_location"],
        "speedtest_server_country": row["server_country"],
        "result_url": row["result_url"],
        "rx_errors_delta": row["rx_errors_delta"],
        "rx_dropped_delta": row["rx_dropped_delta"],
        "rx_missed_errors_delta": row["rx_missed_errors_delta"],
        "tx_errors_delta": row["tx_errors_delta"],
        "tx_dropped_delta": row["tx_dropped_delta"],
        "collisions_delta": row["collisions_delta"],
    }


def export_csv(database_url: str, destination: TextIO) -> int:
    with connect_with_retry(database_url) as connection:
        cursor = connection.execute("SELECT * FROM network_test_runs ORDER BY measured_at")
        column_names = [description.name for description in cursor.description]
        writer = csv.DictWriter(destination, fieldnames=BASE_HEADERS, lineterminator="\n")
        writer.writeheader()
        count = 0
        for values in cursor:
            writer.writerow(_csv_row(dict(zip(column_names, values))))
            count += 1
        return count
