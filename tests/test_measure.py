from netwatch.measure import PING_RTT, PING_SUMMARY, resolve_router_targets, wireless_info


def test_parses_linux_ping_summary():
    output = """100 packets transmitted, 98 received, 2% packet loss, time 49596ms
rtt min/avg/max/mdev = 5.967/15.964/43.073/6.619 ms"""
    summary = PING_SUMMARY.search(output)
    rtt = PING_RTT.search(output)
    assert summary.group("loss") == "2"
    assert rtt.group("average") == "15.964"


def test_resolves_and_deduplicates_auto_gateway():
    assert resolve_router_targets(("auto", "192.168.1.1", "auto"), "192.168.1.254") == [
        "192.168.1.254",
        "192.168.1.1",
    ]


def test_parses_wireless_metrics(monkeypatch):
    output = """Connected to aa:bb:cc:dd:ee:ff (on wlp1s0)
\tsignal: -48 dBm
\ttx bitrate: 866.7 MBit/s
\trx bitrate: 721.5 MBit/s"""
    monkeypatch.setattr("netwatch.measure.run_command", lambda args, timeout: output)
    assert wireless_info("wlp1s0") == {
        "wifi_signal_dbm": -48.0,
        "wifi_tx_bitrate_mbps": 866.7,
        "wifi_rx_bitrate_mbps": 721.5,
    }
