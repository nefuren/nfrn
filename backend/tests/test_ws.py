import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import ORIGIN, WS_URL, login


def test_ws_rejects_without_session(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(WS_URL, headers={"origin": ORIGIN}) as ws:
            ws.receive_json()


def test_ws_rejects_foreign_origin_even_with_session(client):
    login(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(WS_URL, headers={"origin": "http://evil.example"}) as ws:
            ws.receive_json()


def test_ws_rejects_missing_origin(client):
    login(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(WS_URL) as ws:
            ws.receive_json()


def test_ws_streams_with_session_and_origin(client):
    login(client)
    with client.websocket_connect(WS_URL, headers={"origin": ORIGIN}) as ws:
        types = {ws.receive_json()["type"] for _ in range(3)}
    assert {"tick", "slow"} <= types


def test_ws_closes_after_logout(client):
    login(client)
    with client.websocket_connect(WS_URL, headers={"origin": ORIGIN}) as ws:
        ws.receive_json()
        client.post("/api/logout", headers={"origin": ORIGIN})
        with pytest.raises(WebSocketDisconnect):
            for _ in range(50):
                ws.receive_json()


def test_ws_rejects_foreign_host(client):
    login(client)
    with pytest.raises(Exception):
        with client.websocket_connect("ws://evil.example:8787/ws", headers={"origin": ORIGIN}) as ws:
            ws.receive_json()
