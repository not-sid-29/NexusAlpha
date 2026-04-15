"""
core/state_machine.py — Per-Session Finite State Machine for Nexus Alpha.

Every trace_id gets its own FSM instance. The Engine uses this to enforce
deterministic lifecycle transitions. Illegal jumps raise immediately.
"""
import time
import logging
from enum import Enum
from typing import Dict, Optional, Set

logger = logging.getLogger("nexus.fsm")


class SessionState(str, Enum):
    PENDING = "PENDING"
    ROUTING = "ROUTING"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    CODING = "CODING"
    REVIEWING = "REVIEWING"
    DEBUGGING = "DEBUGGING"
    REFLECTING = "REFLECTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class AutonomyMode(str, Enum):
    INTERACTIVE = "INTERACTIVE"
    AUTONOMOUS = "AUTONOMOUS"


class InvalidStateTransition(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


class SessionTerminated(Exception):
    """Raised when an operation is attempted on a terminal session."""
    pass


# ── Transition Table ──────────────────────────────────────────────────────
# Maps each state to the set of states it is allowed to transition into.
# TIMED_OUT and FAILED are reachable from ANY active (non-terminal) state
# via the watchdog or unrecoverable error path — handled separately.
TRANSITION_TABLE: Dict[SessionState, Set[SessionState]] = {
    SessionState.PENDING: {SessionState.ROUTING, SessionState.FAILED},
    SessionState.ROUTING: {SessionState.PLANNING, SessionState.FAILED},
    SessionState.PLANNING: {
        SessionState.AWAITING_APPROVAL,  # Interactive mode
        SessionState.CODING,              # Autonomous mode (skip approval)
        SessionState.FAILED,
    },
    SessionState.AWAITING_APPROVAL: {
        SessionState.CODING,    # Approved
        SessionState.PLANNING,  # Rejected → re-plan with feedback
        SessionState.FAILED,
    },
    SessionState.CODING: {SessionState.REVIEWING, SessionState.DEBUGGING, SessionState.FAILED},
    SessionState.REVIEWING: {
        SessionState.COMPLETED,   # Approved
        SessionState.DEBUGGING,   # Rejected
        SessionState.FAILED,
    },
    SessionState.DEBUGGING: {
        SessionState.CODING,  # Retry loop
        SessionState.FAILED,  # Retries exhausted
    },
    SessionState.COMPLETED: {SessionState.REFLECTING},
    SessionState.FAILED: {SessionState.REFLECTING},
    SessionState.REFLECTING: set(),   # Terminal
    SessionState.TIMED_OUT: set(),    # Terminal
}

TERMINAL_STATES = {SessionState.REFLECTING, SessionState.TIMED_OUT}
ACTIVE_STATES = set(SessionState) - TERMINAL_STATES


class Session:
    """
    Represents a single task execution session with its own FSM lifecycle.
    """
    def __init__(
        self,
        trace_id: str,
        autonomy_mode: AutonomyMode = AutonomyMode.INTERACTIVE,
        phase_ttl_seconds: float = 120.0,
        max_debug_retries: int = 3,
        max_review_rejections: int = 3,
    ):
        self.trace_id = trace_id
        self.autonomy_mode = autonomy_mode
        self.state = SessionState.PENDING
        self.phase_ttl_seconds = phase_ttl_seconds
        self.max_debug_retries = max_debug_retries
        self.max_review_rejections = max_review_rejections

        # Counters
        self.debug_retry_count = 0
        self.review_rejection_count = 0

        # Timestamps
        self.created_at = time.monotonic()
        self.last_transition_at = self.created_at

        # Audit log
        self.transition_history: list = [(self.state, self.created_at)]

        # Buffered result for WS reconnect delivery
        self.buffered_result: Optional[dict] = None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def elapsed_in_phase(self) -> float:
        return time.monotonic() - self.last_transition_at

    @property
    def is_timed_out(self) -> bool:
        if self.is_terminal:
            return False
        return self.elapsed_in_phase > self.phase_ttl_seconds

    def transition(self, target: SessionState) -> SessionState:
        """
        Attempt a state transition. Raises InvalidStateTransition if illegal.
        Handles watchdog timeouts and retry counter enforcement.
        """
        if self.is_terminal:
            raise SessionTerminated(
                f"[{self.trace_id}] Session is in terminal state {self.state.value}. "
                f"No further transitions allowed."
            )

        # ── Watchdog: TIMED_OUT is reachable from any active state ──
        if target == SessionState.TIMED_OUT:
            self._do_transition(target)
            return self.state

        # ── FAILED is reachable from any active state ──
        if target == SessionState.FAILED:
            self._do_transition(target)
            return self.state

        # ── Normal transition: must be in the table ──
        allowed = TRANSITION_TABLE.get(self.state, set())
        if target not in allowed:
            raise InvalidStateTransition(
                f"[{self.trace_id}] Illegal transition: "
                f"{self.state.value} → {target.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        # ── Retry counter enforcement ──
        if self.state == SessionState.DEBUGGING and target == SessionState.CODING:
            self.debug_retry_count += 1
            if self.debug_retry_count > self.max_debug_retries:
                logger.error(
                    f"[{self.trace_id}] Debug retries exhausted "
                    f"({self.debug_retry_count}/{self.max_debug_retries}). "
                    f"Forcing FAILED."
                )
                self._do_transition(SessionState.FAILED)
                return self.state

        if self.state == SessionState.REVIEWING and target == SessionState.DEBUGGING:
            self.review_rejection_count += 1
            if self.review_rejection_count > self.max_review_rejections:
                if self.autonomy_mode == AutonomyMode.AUTONOMOUS:
                    logger.warning(
                        f"[{self.trace_id}] Review rejections exceeded "
                        f"({self.review_rejection_count}/{self.max_review_rejections}). "
                        f"Escalating to INTERACTIVE mode."
                    )
                    self.autonomy_mode = AutonomyMode.INTERACTIVE

        # ── Autonomy mode: skip AWAITING_APPROVAL ──
        if (
            self.state == SessionState.PLANNING
            and target == SessionState.AWAITING_APPROVAL
            and self.autonomy_mode == AutonomyMode.AUTONOMOUS
        ):
            logger.info(f"[{self.trace_id}] Autonomous mode: skipping AWAITING_APPROVAL → CODING")
            self._do_transition(SessionState.CODING)
            return self.state

        self._do_transition(target)
        return self.state

    def check_watchdog(self) -> bool:
        """
        Called periodically. If the session has exceeded TTL in current phase,
        force-transitions to TIMED_OUT. Returns True if timeout was triggered.
        """
        if self.is_timed_out:
            logger.critical(
                f"[{self.trace_id}] Watchdog: phase {self.state.value} "
                f"exceeded TTL ({self.phase_ttl_seconds}s). Forcing TIMED_OUT."
            )
            self._do_transition(SessionState.TIMED_OUT)
            return True
        return False

    def _do_transition(self, target: SessionState):
        old = self.state
        self.state = target
        self.last_transition_at = time.monotonic()
        self.transition_history.append((target, self.last_transition_at))
        logger.info(f"[{self.trace_id}] State: {old.value} → {target.value}")


class SessionRegistry:
    """
    Central registry of all active and completed sessions.
    The Engine interacts with sessions exclusively through this registry.
    """
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create_session(
        self,
        trace_id: str,
        autonomy_mode: AutonomyMode = AutonomyMode.INTERACTIVE,
        **kwargs,
    ) -> Session:
        if trace_id in self._sessions:
            raise ValueError(f"Session {trace_id} already exists.")
        session = Session(trace_id=trace_id, autonomy_mode=autonomy_mode, **kwargs)
        self._sessions[trace_id] = session
        return session

    def get_session(self, trace_id: str) -> Optional[Session]:
        return self._sessions.get(trace_id)

    def get_active_sessions(self) -> list:
        return [s for s in self._sessions.values() if not s.is_terminal]

    def run_watchdog_sweep(self) -> list:
        """
        Sweep all active sessions and timeout any that have exceeded their TTL.
        Returns list of timed-out trace_ids.
        """
        timed_out = []
        for session in self.get_active_sessions():
            if session.check_watchdog():
                timed_out.append(session.trace_id)
        return timed_out
