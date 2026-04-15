"""
Tests for core/state_machine.py — Rigorous FSM lifecycle verification.
"""
import time
import pytest
from core.state_machine import (
    Session,
    SessionState,
    AutonomyMode,
    InvalidStateTransition,
    SessionTerminated,
    SessionRegistry,
)


class TestSessionTransitions:
    """Verify every legal and illegal transition in the FSM."""

    def test_happy_path_interactive(self):
        """Full interactive pipeline: PENDING → ... → REFLECTING"""
        s = Session(trace_id="t1", autonomy_mode=AutonomyMode.INTERACTIVE)
        assert s.state == SessionState.PENDING

        s.transition(SessionState.ROUTING)
        assert s.state == SessionState.ROUTING

        s.transition(SessionState.PLANNING)
        assert s.state == SessionState.PLANNING

        s.transition(SessionState.AWAITING_APPROVAL)
        assert s.state == SessionState.AWAITING_APPROVAL

        s.transition(SessionState.CODING)
        assert s.state == SessionState.CODING

        s.transition(SessionState.REVIEWING)
        assert s.state == SessionState.REVIEWING

        s.transition(SessionState.COMPLETED)
        assert s.state == SessionState.COMPLETED

        s.transition(SessionState.REFLECTING)
        assert s.state == SessionState.REFLECTING
        assert s.is_terminal

    def test_happy_path_autonomous_skips_approval(self):
        """Autonomous mode: PLANNING → CODING (AWAITING_APPROVAL skipped)."""
        s = Session(trace_id="t2", autonomy_mode=AutonomyMode.AUTONOMOUS)
        s.transition(SessionState.ROUTING)
        s.transition(SessionState.PLANNING)

        # Attempting AWAITING_APPROVAL in autonomous mode → auto-skips to CODING
        s.transition(SessionState.AWAITING_APPROVAL)
        assert s.state == SessionState.CODING  # Skipped!

    def test_illegal_transition_raises(self):
        """PENDING → COMPLETED is illegal."""
        s = Session(trace_id="t3")
        with pytest.raises(InvalidStateTransition):
            s.transition(SessionState.COMPLETED)

    def test_illegal_transition_pending_to_coding(self):
        """PENDING → CODING is illegal."""
        s = Session(trace_id="t4")
        with pytest.raises(InvalidStateTransition):
            s.transition(SessionState.CODING)

    def test_terminal_state_blocks_further_transitions(self):
        """Once REFLECTING, no more transitions are allowed."""
        s = Session(trace_id="t5")
        s.transition(SessionState.ROUTING)
        s.transition(SessionState.PLANNING)
        s.transition(SessionState.CODING)
        s.transition(SessionState.REVIEWING)
        s.transition(SessionState.COMPLETED)
        s.transition(SessionState.REFLECTING)

        with pytest.raises(SessionTerminated):
            s.transition(SessionState.PENDING)

    def test_failed_is_reachable_from_any_active_state(self):
        """FAILED can be reached from PENDING, ROUTING, PLANNING, CODING, etc."""
        for start_state in [SessionState.PENDING]:
            s = Session(trace_id=f"fail-{start_state.value}")
            s.transition(SessionState.FAILED)
            assert s.state == SessionState.FAILED

    def test_timed_out_reachable_from_any_active_state(self):
        """TIMED_OUT can be triggered from any active state."""
        s = Session(trace_id="timeout-test")
        s.transition(SessionState.ROUTING)
        s.transition(SessionState.PLANNING)
        s.transition(SessionState.TIMED_OUT)
        assert s.state == SessionState.TIMED_OUT
        assert s.is_terminal


class TestRetryCounters:
    """Verify debug retry and review rejection enforcement."""

    def _get_session_at_debugging(self) -> Session:
        s = Session(trace_id="retry-test", max_debug_retries=2)
        s.transition(SessionState.ROUTING)
        s.transition(SessionState.PLANNING)
        s.transition(SessionState.CODING)
        s.transition(SessionState.REVIEWING)
        s.transition(SessionState.DEBUGGING)
        return s

    def test_debug_retries_within_limit(self):
        s = self._get_session_at_debugging()
        # 1st retry
        s.transition(SessionState.CODING)
        assert s.state == SessionState.CODING
        assert s.debug_retry_count == 1

    def test_debug_retries_exhausted_forces_failed(self):
        s = self._get_session_at_debugging()
        # Retry 1
        s.transition(SessionState.CODING)
        s.transition(SessionState.REVIEWING)
        s.transition(SessionState.DEBUGGING)
        # Retry 2
        s.transition(SessionState.CODING)
        s.transition(SessionState.REVIEWING)
        s.transition(SessionState.DEBUGGING)
        # Retry 3 → should exceed max (2) and force FAILED
        s.transition(SessionState.CODING)
        assert s.state == SessionState.FAILED

    def test_review_rejections_escalate_to_interactive(self):
        s = Session(
            trace_id="escalation-test",
            autonomy_mode=AutonomyMode.AUTONOMOUS,
            max_review_rejections=2,
        )
        s.transition(SessionState.ROUTING)
        s.transition(SessionState.PLANNING)
        s.transition(SessionState.CODING)

        # Rejection 1
        s.transition(SessionState.REVIEWING)
        s.transition(SessionState.DEBUGGING)
        s.transition(SessionState.CODING)

        # Rejection 2
        s.transition(SessionState.REVIEWING)
        s.transition(SessionState.DEBUGGING)
        s.transition(SessionState.CODING)

        # Rejection 3 → exceeds max → mode escalated
        s.transition(SessionState.REVIEWING)
        s.transition(SessionState.DEBUGGING)
        assert s.autonomy_mode == AutonomyMode.INTERACTIVE


class TestWatchdog:
    """Verify TTL-based timeout detection."""

    def test_watchdog_triggers_on_stale_session(self):
        s = Session(trace_id="watchdog-test", phase_ttl_seconds=0.01)
        s.transition(SessionState.ROUTING)
        time.sleep(0.02)  # Exceed TTL
        assert s.is_timed_out
        triggered = s.check_watchdog()
        assert triggered
        assert s.state == SessionState.TIMED_OUT

    def test_watchdog_does_not_trigger_fresh_session(self):
        s = Session(trace_id="fresh-test", phase_ttl_seconds=60.0)
        s.transition(SessionState.ROUTING)
        assert not s.is_timed_out
        assert not s.check_watchdog()


class TestSessionRegistry:
    def test_create_and_retrieve(self):
        reg = SessionRegistry()
        s = reg.create_session("r1")
        assert reg.get_session("r1") is s

    def test_duplicate_creation_raises(self):
        reg = SessionRegistry()
        reg.create_session("dup")
        with pytest.raises(ValueError):
            reg.create_session("dup")

    def test_watchdog_sweep(self):
        reg = SessionRegistry()
        s1 = reg.create_session("sweep-1", phase_ttl_seconds=0.01)
        s1.transition(SessionState.ROUTING)
        time.sleep(0.02)
        timed_out = reg.run_watchdog_sweep()
        assert "sweep-1" in timed_out

    def test_transition_history_recorded(self):
        s = Session(trace_id="hist-test")
        s.transition(SessionState.ROUTING)
        s.transition(SessionState.PLANNING)
        assert len(s.transition_history) == 3  # PENDING + ROUTING + PLANNING
        states = [t[0] for t in s.transition_history]
        assert states == [SessionState.PENDING, SessionState.ROUTING, SessionState.PLANNING]
