import json
from datetime import datetime, timezone

from netwatch.database import BASE_HEADERS, _csv_row


def test_csv_row_has_report_fields():
    row = {
        "measured_at": datetime(2026, 11, 18, tzinfo=timezone.utc),
        "interface_name": "eno1", "link_speed_mbps": 1000, "duplex": "full",
        "wifi_signal_dbm": None, "wifi_tx_bitrate_mbps": None, "wifi_rx_bitrate_mbps": None,
        "default_gateway": "192.168.1.254",
        "router_results": [{"target": "192.168.1.254", "packet_loss_pct": 0.0,
                            "latency_min_ms": 1.0, "latency_avg_ms": 2.0,
                            "latency_max_ms": 3.0, "jitter_ms": 0.5}],
        "dns_target": "9.9.9.9",
        "dns_result": {"packet_loss_pct": 2.0, "latency_min_ms": 6.0,
                       "latency_avg_ms": 16.0, "latency_max_ms": 43.0, "jitter_ms": 6.6},
        "dns_candidates": [], "download_mbps": 325.0, "upload_mbps": 100.0,
        "idle_latency_ms": 7.2, "idle_jitter_ms": 1.1,
        "loaded_download_latency_ms": 19.0, "loaded_upload_latency_ms": 17.0,
        "speedtest_packet_loss_pct": 0.76, "isp": "Example", "external_ip": "203.0.113.1",
        "server_id": 1, "server_name": "Server", "server_location": "Oslo",
        "server_country": "Norway", "result_url": "https://example.test/result",
        "rx_errors_delta": 0, "rx_dropped_delta": 0, "rx_missed_errors_delta": 0,
        "tx_errors_delta": 0, "tx_dropped_delta": 0, "collisions_delta": 0,
    }
    exported = _csv_row(row)
    assert list(exported) == BASE_HEADERS
    assert exported["download_mbps"] == 325.0
    assert exported["router_packet_loss_pct"] == 0.0
