import socket
from collections import namedtuple

from app.collectors.geoip import GeoIP
from app.collectors.network import NetRate, aggregate_remotes, listening_ports, parse_connections
from app.collectors.system import ProcessNames

Addr = namedtuple("Addr", "ip port")
Conn = namedtuple("Conn", "fd family type laddr raddr status pid")
T, U = socket.SOCK_STREAM, socket.SOCK_DGRAM
V4 = socket.AF_INET


class FakeNames(ProcessNames):
    def name(self, pid):
        return {10: "chrome.exe", 20: "svchost.exe"}.get(pid, "?")


RAW = [
    Conn(1, V4, T, Addr("192.168.1.5", 50000), Addr("93.184.216.34", 443), "ESTABLISHED", 10),
    Conn(2, V4, T, Addr("192.168.1.5", 50001), Addr("93.184.216.34", 443), "ESTABLISHED", 10),
    Conn(3, V4, T, Addr("192.168.1.5", 50002), Addr("45.33.32.156", 4444), "ESTABLISHED", 20),
    Conn(4, V4, T, Addr("127.0.0.1", 50003), Addr("127.0.0.1", 8787), "ESTABLISHED", 10),
    Conn(5, V4, T, Addr("192.168.1.5", 50004), Addr("93.184.216.34", 443), "TIME_WAIT", 10),
    Conn(6, V4, T, Addr("0.0.0.0", 445), (), "LISTEN", 4),
    Conn(7, V4, T, Addr("127.0.0.1", 8787), (), "LISTEN", 10),
    Conn(8, V4, U, Addr("0.0.0.0", 5353), (), "NONE", 20),
    Conn(9, V4, T, Addr("0.0.0.0", 445), (), "LISTEN", 4),
    Conn(10, V4, T, Addr("192.168.1.5", 50005), Addr("192.168.1.1", 53), "ESTABLISHED", 20),
]


class FakeGeo(GeoIP):
    def __init__(self):
        super().__init__(reader=None)

    def _lookup_public(self, ip):
        return {"93.184.216.34": "US", "45.33.32.156": "RU"}.get(ip, "??")


def test_parse_connections_skips_loopback_and_non_established():
    conns = parse_connections(RAW, FakeNames())
    assert [(c.remote_ip, c.remote_port) for c in conns] == [
        ("93.184.216.34", 443), ("93.184.216.34", 443), ("45.33.32.156", 4444), ("192.168.1.1", 53)
    ]
    assert conns[0].process == "chrome.exe"


def test_aggregate_remotes():
    remotes = aggregate_remotes(parse_connections(RAW, FakeNames()), FakeGeo())
    top = remotes[0]
    assert top == {"ip": "93.184.216.34", "country": "US", "count": 2, "ports": [443],
                   "processes": ["chrome.exe"], "private": False}
    lan = next(r for r in remotes if r["ip"] == "192.168.1.1")
    assert lan["country"] == "LAN" and lan["private"] is True


def test_listening_ports_dedup_and_exposed():
    ports = listening_ports(RAW, FakeNames())
    assert [(p["proto"], p["address"], p["port"], p["exposed"]) for p in ports] == [
        ("tcp", "0.0.0.0", 445, True),
        ("udp", "0.0.0.0", 5353, True),
        ("tcp", "127.0.0.1", 8787, False),
    ]


def test_net_rate():
    Counters = namedtuple("Counters", "bytes_recv bytes_sent")
    values = iter([Counters(1000, 500), Counters(3000, 1500)])
    times = iter([10.0, 12.0])
    rate = NetRate(counters=lambda: next(values), clock=lambda: next(times))
    s = rate.sample()
    assert s == {"rx_bps": 1000.0, "tx_bps": 500.0, "rx_total": 3000, "tx_total": 1500}


def test_geoip_special_ranges():
    g = GeoIP(reader=None)
    assert g.lookup("127.0.0.1") == "LOCAL"
    assert g.lookup("::1") == "LOCAL"
    assert g.lookup("10.0.0.1") == "LAN"
    assert g.lookup("fe80::1") == "LAN"
    assert g.lookup("8.8.8.8") == "??"  # DB なし
    assert g.lookup("not-an-ip") == "??"


def test_geoip_with_reader():
    class R:
        def get(self, ip):
            return {"country": {"iso_code": "JP"}} if ip == "1.1.1.1" else None

    g = GeoIP(reader=R())
    assert g.lookup("1.1.1.1") == "JP"
    assert g.lookup("1.0.0.1") == "??"


def test_geoip_missing_file(tmp_path):
    g = GeoIP.from_path(tmp_path / "missing.mmdb")
    assert g.available is False and g.lookup("8.8.8.8") == "??"
