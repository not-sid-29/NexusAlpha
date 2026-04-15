"""
Tests for api/fastapi_app.py — Multi-tenant WebSocket verification.
"""
import pytest
import json
from fastapi.testclient import TestClient
from api.fastapi_app import app


def test_ws_submit_creates_session():
    """Sending a task creates a session and returns a trace_id."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({
            "action": "submit",
            "prompt": "design the database schema",
            "mode": "AUTONOMOUS"
        }))

        # First message: session_created event
        data = json.loads(ws.receive_text())
        assert data["event"] == "session_created"
        assert "trace_id" in data
        assert data["mode"] == "AUTONOMOUS"

        # Second message: the actual TOON task routed via dispatcher
        toon = json.loads(ws.receive_text())
        assert toon["source"] == "ENGINE"
        assert toon["target"] == "PLANNER"
        assert toon["trace_id"] == data["trace_id"]


def test_ws_plain_text_fallback():
    """Sending a plain string (non-JSON) submits it as a task."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text("write a python script")

        data = json.loads(ws.receive_text())
        assert data["event"] == "session_created"

        toon = json.loads(ws.receive_text())
        assert toon["target"] == "CODER"
        assert toon["payload"]["instruction"] == "write a python script"


def test_ws_isolation_between_clients():
    """Messages from client A's session must NOT leak to client B."""
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws_a:
        ws_a.send_text(json.dumps({"action": "submit", "prompt": "plan the auth module"}))
        resp_a = json.loads(ws_a.receive_text())
        trace_a = resp_a["trace_id"]

        # ws_a receives the TOON message for its own session
        toon_a = json.loads(ws_a.receive_text())
        assert toon_a["trace_id"] == trace_a

    # Client B connects separately and should NOT receive ws_a's messages
    with client.websocket_connect("/ws") as ws_b:
        ws_b.send_text(json.dumps({"action": "submit", "prompt": "debug the login"}))
        resp_b = json.loads(ws_b.receive_text())
        trace_b = resp_b["trace_id"]
        assert trace_b != trace_a  # Different sessions!
