import asyncio
import json
from datetime import UTC, datetime

from conftest import TOKEN

from app.collectors.history import LoginEvent
from app.config import Settings
from app.monitor import Monitor


class FakeLogins:
    def fetch(self):
        now = datetime.now(UTC)
        events = [LoginEvent(ts=now, kind="failure", user="<b>x</b>", source_ip="203.0.113.5",
                             detail="t", key=f"k{i}") for i in range(3)]
        return events, {"state": "ok", "message": "", "source": "fake"}


class BrokenLogins:
    def fetch(self):
        return [], {"state": "no_permission", "message": "権限なし", "source": "fake"}


class FakeAudit:
    def run_once(self):
        return {"last_run": None, "targets": [], "findings": [], "counts": {}}


def make(tmp_path, logins):
    s = Settings(token=TOKEN, geoip_db=None, _env_file=None)
    return Monitor(s, login_source=logins, audit_runner=FakeAudit())


def test_monitor_produces_tick_and_slow(tmp_path):
    async def go():
        m = make(tmp_path, FakeLogins())
        await m.start()
        try:
            return m.tick(), m.slow()
        finally:
            await m.stop()

    tick, slow = asyncio.run(go())
    assert tick["type"] == "tick"
    assert 0 <= tick["system"]["cpu"] <= 100
    assert {"rx_bps", "tx_bps"} <= tick["net"].keys()
    assert isinstance(tick["remotes"], list)
    assert slow["type"] == "slow"
    assert slow["logins"]["failures_1h"] == 3
    assert slow["logins"]["recent"][0]["user"] == "<b>x</b>"  # 生の文字列のまま
    assert len(slow["logins"]["failures_per_minute"]) == 60
    assert slow["score"] == tick["score"]  # tick は常に最新のスコアを載せる
    json.dumps(tick)
    json.dumps(slow, ensure_ascii=False)


def test_monitor_survives_unreadable_logs(tmp_path):
    async def go():
        m = make(tmp_path, BrokenLogins())
        await m.start()
        try:
            return m.slow()
        finally:
            await m.stop()

    slow = asyncio.run(go())
    assert slow["logins"]["status"]["state"] == "no_permission"
    assert slow["logins"]["failures_1h"] == 0
