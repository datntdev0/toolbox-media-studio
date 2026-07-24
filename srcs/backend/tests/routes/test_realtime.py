"""WebSocket route contract tests."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD


def test_websocket_requires_a_valid_access_token(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/api/ws"):
            pass

    assert error.value.code == 4401


def test_websocket_supports_typed_bidirectional_messages(client: TestClient) -> None:
    token = _login(client)

    with client.websocket_connect(f"/api/ws?accessToken={token}") as socket:
        ready = socket.receive_json()
        socket.send_json(
            {
                "type": "connection.ping",
                "payload": {"clientTime": "2026-07-24T00:00:00Z"},
            }
        )
        pong = socket.receive_json()
        socket.send_json(
            {
                "type": "connection.echo",
                "payload": {"message": "hello"},
            }
        )
        echo = socket.receive_json()

    assert ready["type"] == "connection.ready"
    assert ready["payload"]["userId"]
    assert pong["type"] == "connection.pong"
    assert pong["payload"]["clientTime"] == "2026-07-24T00:00:00Z"
    assert echo == {
        "type": "connection.echo",
        "payload": {"message": "hello"},
    }


def test_hub_can_publish_backend_events_to_a_connected_client(client: TestClient) -> None:
    token = _login(client)

    with client.websocket_connect(f"/api/ws?accessToken={token}") as socket:
        socket.receive_json()
        client.app.state.realtime_hub.publish(
            "scraping.updated",
            {"scrapingId": "scraping-1"},
        )
        message = socket.receive_json()

    assert message == {
        "type": "scraping.updated",
        "payload": {"scrapingId": "scraping-1"},
    }


def _login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]
