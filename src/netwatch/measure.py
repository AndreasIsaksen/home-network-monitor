from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings


PING_SUMMARY = re.compile(
    r"(?P<sent>\d+) packets transmitted, (?P<received>\d+) received, "
    r"(?P<loss>[\d.]+)% packet loss"
)
PING_RTT = re.compile(
    r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = "
    r"(?P<minimum>[\d.]+)/(?P<average>[\d.]+)/(?P<maximum>[\d.]+)/(?P<jitter>[\d.]+) ms"
)


@dataclass
class PingResult:
    target: str
    sent: int
    received: int
    packet_loss_pct: float
    latency_min_ms: float | None
    latency_avg_ms: float | None
    latency_max_ms: float | None
    jitter_ms: float | None


def run_command(args: list[str], timeout: int) -> str:
    completed = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(args)}\n{completed.stdout}")
    return completed.stdout


def default_route() -> tuple[str, str]:
    output = run_command(["ip", "-4", "route", "show", "default"], timeout=10)
    match = re.search(r"default via (?P<gateway>\S+) dev (?P<interface>\S+)", output)
    if not match:
        raise RuntimeError(f"Could not determine default IPv4 route: {output.strip()}")
    return match.group("gateway"), match.group("interface")


def ping(target: str, count: int, interval: float) -> PingResult:
    timeout = max(15, int(count * interval) + 10)
    output = run_command(
        ["ping", "-n", "-q", "-c", str(count), "-i", str(interval), "-W", "2", target],
        timeout=timeout,
    )
    summary = PING_SUMMARY.search(output)
    if not summary:
        raise RuntimeError(f"Could not parse ping output for {target}: {output.strip()}")
    rtt = PING_RTT.search(output)
    return PingResult(
        target=target,
        sent=int(summary.group("sent")),
        received=int(summary.group("received")),
        packet_loss_pct=float(summary.group("loss")),
        latency_min_ms=float(rtt.group("minimum")) if rtt else None,
        latency_avg_ms=float(rtt.group("average")) if rtt else None,
        latency_max_ms=float(rtt.group("maximum")) if rtt else None,
        jitter_ms=float(rtt.group("jitter")) if rtt else None,
    )


def read_text(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except (OSError, ValueError):
        return None


def interface_info(interface: str) -> dict[str, Any]:
    base = Path("/sys/class/net") / interface
    stats = base / "statistics"
    counters = {}
    for name in ("rx_errors", "rx_dropped", "rx_missed_errors", "tx_errors", "tx_dropped", "collisions"):
        value = read_text(stats / name)
        counters[name] = int(value) if value and value.isdigit() else None
    speed = read_text(base / "speed")
    return {
        "interface_name": interface,
        "link_speed_mbps": int(speed) if speed and speed.lstrip("-").isdigit() and int(speed) >= 0 else None,
        "duplex": read_text(base / "duplex"),
        **counters,
    }


def wireless_info(interface: str) -> dict[str, float | None]:
    """Return negotiated Wi-Fi radio metrics, or nulls for wired interfaces."""
    try:
        output = run_command(["iw", "dev", interface, "link"], timeout=10)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        output = ""

    def value(pattern: str) -> float | None:
        match = re.search(pattern, output, re.MULTILINE)
        return float(match.group(1)) if match else None

    return {
        "wifi_signal_dbm": value(r"^\s*signal:\s*(-?[\d.]+)\s*dBm"),
        "wifi_tx_bitrate_mbps": value(r"^\s*tx bitrate:\s*([\d.]+)\s*MBit/s"),
        "wifi_rx_bitrate_mbps": value(r"^\s*rx bitrate:\s*([\d.]+)\s*MBit/s"),
    }


def resolve_router_targets(configured: tuple[str, ...], gateway: str) -> list[str]:
    resolved: list[str] = []
    for target in configured:
        value = gateway if target.lower() == "auto" else target
        if value not in resolved:
            resolved.append(value)
    return resolved


def choose_dns(settings: Settings) -> tuple[PingResult, list[PingResult]]:
    probes: list[PingResult] = []
    for target in settings.dns_candidates:
        try:
            probes.append(ping(target, settings.dns_selection_ping_count, settings.ping_interval_seconds))
        except Exception:
            probes.append(PingResult(target, settings.dns_selection_ping_count, 0, 100.0, None, None, None, None))
    reachable = [probe for probe in probes if probe.latency_avg_ms is not None]
    if not reachable:
        raise RuntimeError("No configured public DNS target responded")
    selected = min(reachable, key=lambda probe: (probe.latency_avg_ms, probe.packet_loss_pct))
    final = ping(selected.target, settings.dns_ping_count, settings.ping_interval_seconds)
    return final, probes


def speedtest(server_id: str | None) -> dict[str, Any]:
    args = ["speedtest", "--accept-license", "--accept-gdpr", "--format=json"]
    if server_id:
        args.extend(["--server-id", server_id])
    output = run_command(args, timeout=180)
    try:
        return json.loads(output[output.find("{"):])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse speedtest output: {output}") from exc


def collect(settings: Settings) -> dict[str, Any]:
    gateway, interface = default_route()
    before = interface_info(interface)
    wifi = wireless_info(interface)
    router_results = [
        asdict(ping(target, settings.router_ping_count, settings.ping_interval_seconds))
        for target in resolve_router_targets(settings.router_targets, gateway)
    ]
    dns_result, dns_probes = choose_dns(settings)
    ookla = speedtest(settings.speedtest_server_id)
    after = interface_info(interface)

    counter_deltas = {}
    for key in ("rx_errors", "rx_dropped", "rx_missed_errors", "tx_errors", "tx_dropped", "collisions"):
        old, new = before.get(key), after.get(key)
        counter_deltas[f"{key}_delta"] = new - old if old is not None and new is not None else None

    download = ookla.get("download", {})
    upload = ookla.get("upload", {})
    ping_data = ookla.get("ping", {})
    server = ookla.get("server", {})
    iface = ookla.get("interface", {})
    result = ookla.get("result", {})

    return {
        "measured_at": datetime.now(timezone.utc),
        **{key: before.get(key) for key in ("interface_name", "link_speed_mbps", "duplex")},
        **wifi,
        "default_gateway": gateway,
        "router_results": router_results,
        "dns_target": dns_result.target,
        "dns_result": asdict(dns_result),
        "dns_candidates": [asdict(probe) for probe in dns_probes],
        "download_mbps": download.get("bandwidth", 0) * 8 / 1_000_000,
        "upload_mbps": upload.get("bandwidth", 0) * 8 / 1_000_000,
        "idle_latency_ms": ping_data.get("latency"),
        "idle_jitter_ms": ping_data.get("jitter"),
        "loaded_download_latency_ms": download.get("latency", {}).get("iqm"),
        "loaded_upload_latency_ms": upload.get("latency", {}).get("iqm"),
        "speedtest_packet_loss_pct": ookla.get("packetLoss"),
        "isp": ookla.get("isp"),
        "external_ip": iface.get("externalIp"),
        "server_id": server.get("id"),
        "server_name": server.get("name"),
        "server_location": server.get("location"),
        "server_country": server.get("country"),
        "result_url": result.get("url"),
        **counter_deltas,
        "raw_speedtest": ookla,
    }
