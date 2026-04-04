from naia_relay.core import (
    ExecutionState,
    ExecutionTracker,
    PendingRequest,
    RequestTracker,
    SessionManager,
    SessionState,
    from_json,
    new_execution_id,
    new_message_id,
    new_relay_id,
    new_request_id,
    new_session_id,
    to_json,
)


def test_identifier_generation_has_expected_prefixes() -> None:
    assert new_message_id().startswith("msg_")
    assert new_request_id().startswith("req_")
    assert new_execution_id().startswith("exec_")
    assert new_session_id().startswith("sess_")
    assert new_relay_id().startswith("relay_")


def test_request_tracker_tracks_concurrent_requests() -> None:
    tracker = RequestTracker()
    first = PendingRequest(request_id="req_1", message_id="msg_1")
    second = PendingRequest(request_id="req_2", message_id="msg_2")

    tracker.add(first)
    tracker.add(second)

    assert tracker.count() == 2
    assert tracker.get("req_1") == first
    assert tracker.pop("req_2") == second
    assert tracker.count() == 1


def test_execution_tracker_updates_status() -> None:
    tracker = ExecutionTracker()
    state = ExecutionState(execution_id="exec_1", tool_name="demo")
    tracker.add(state)

    updated = tracker.update_status("exec_1", "running")

    assert updated.status == "running"
    assert tracker.count() == 1


def test_session_manager_tracks_by_kind() -> None:
    manager = SessionManager()
    manager.add(SessionState(session_id="sess_1", kind="mcp"))
    manager.add(SessionState(session_id="sess_2", kind="tep"))

    assert manager.count() == 2
    assert manager.count(kind="mcp") == 1


def test_json_helpers_round_trip() -> None:
    payload = {"hello": "world", "count": 1}

    encoded = to_json(payload)
    decoded = from_json(encoded)

    assert decoded == payload
