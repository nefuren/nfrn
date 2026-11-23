import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TOKEN = "test-token-" + "z" * 40
BASE = "http://127.0.0.1:8787"
ORIGIN = "http://127.0.0.1:8787"
WS_URL = "ws://127.0.0.1:8787/ws"


class FakeMonitor:
    def __init__(self):
        self.started = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    def tick(self):
        return {"type": "tick", "cpu": 1.0}

    def slow(self):
        return {"type": "slow", "ports": []}

    def snapshot(self):
        return {"tick": self.tick(), "slow": self.slow()}


@pytest.fixture
def settings(tmp_path):
    return Settings(token=TOKEN, frontend_dist=tmp_path / "nodist", _env_file=None)


@pytest.fixture
def client(settings):
    app = create_app(settings, monitor=FakeMonitor(), tick_interval=0.05)
    with TestClient(app, base_url=BASE) as c:
        yield c


def login(client, token=TOKEN):
    return client.post("/api/login", json={"token": token}, headers={"origin": ORIGIN})
