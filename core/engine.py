"""
core/engine.py — Nexus Orchestration Engine (Production-Grade).

This is NOT a simple pass-through router. It is an active Session Manager
that spawns per-session FSM instances, enforces state transitions on
every TOON message callback, and handles timeouts via periodic watchdog sweeps.
"""
import asyncio
import logging
from typing import Optional

from bus.dispatcher import AsyncDispatcher
from bus.protocol import create_task_message
from bus.tracing import generate_trace_id
from core.router import BaseRouter
from core.state_machine import (
    SessionRegistry,
    SessionState,
    AutonomyMode,
    InvalidStateTransition,
    SessionTerminated,
)
from schemas.messages import TOONMessage, MessageType
from core.guards import InputGuard, OutputGuard

logger = logging.getLogger("nexus.engine")


class NexusEngine:
    """
    The Orchestration brain. Manages session lifecycles via FSM,
    hooks the WebSocket interface to the TOON bus, and runs a periodic
    watchdog to kill stalled sessions.
    """

    def __init__(self, dispatcher: AsyncDispatcher):
        self.dispatcher = dispatcher
        self.router = BaseRouter()
        self.registry = SessionRegistry()
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_interval = 5.0  # seconds between sweeps

    async def start(self):
        """Start the watchdog background task."""
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info("[ENGINE] Watchdog started.")

    async def shutdown(self):
        """Graceful shutdown: cancel watchdog."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        logger.info("[ENGINE] Shutdown complete.")

    async def submit_user_prompt(
        self,
        user_prompt: str,
        autonomy_mode: AutonomyMode = AutonomyMode.INTERACTIVE,
        client_id: Optional[str] = None,
    ) -> str:
        """
        Entrypoint for external interfaces (WebSockets/TUI).
        Creates a traced session with its own FSM, routes to the correct
        first agent in the DAG.
        """
        # ── Layer 1: Input Validation ──
        if not InputGuard.validate_input(user_prompt):
            raise ValueError("Dangerous input pattern detected in prompt.")

        trace_id = generate_trace_id()
        # Spawn session FSM
        session = self.registry.create_session(
            trace_id=trace_id,
            autonomy_mode=autonomy_mode,
        )

        # Transition: PENDING → ROUTING
        session.transition(SessionState.ROUTING)
        target_agent = self.router.classify_task(user_prompt)

        # Transition: ROUTING → PLANNING
        session.transition(SessionState.PLANNING)

        logger.info(
            f"[{trace_id}] Engine routing task to {target_agent} "
            f"(mode={autonomy_mode.value})"
        )

        msg = create_task_message(
            source="ENGINE",
            target=target_agent,
            payload_data={"instruction": user_prompt},
            trace_id=trace_id,
        )
        await self.dispatcher.publish(msg)
        return trace_id

    async def handle_agent_result(self, message: TOONMessage):
        """
        Callback invoked when an agent publishes a RESULT or ERROR back
        to the bus. Drives the session FSM forward.
        """
        session = self.registry.get_session(message.trace_id)
        if not session:
            logger.error(f"[ENGINE] No session for trace_id={message.trace_id}")
            return

        try:
            if message.msg_type == MessageType.ERROR:
                if session.state == SessionState.CODING:
                    session.transition(SessionState.REVIEWING)
                    session.transition(SessionState.DEBUGGING)
                elif session.state == SessionState.DEBUGGING:
                    # Retry → back to coding (counter enforced inside FSM)
                    session.transition(SessionState.CODING)
                else:
                    session.transition(SessionState.FAILED)

            elif message.msg_type == MessageType.RESULT:
                # ── Layer 4: Output Validation (for Coder) ──
                if message.source.upper() == "CODER":
                    code = message.payload.get("code")
                    if code:
                        is_valid, err = OutputGuard.validate_code(code)
                        if not is_valid:
                            logger.error(f"[{message.trace_id}] OutputGuard rejected Coder result: {err}")
                            # Transition back to debugging/failed if broken code is emitted
                            session.transition(SessionState.DEBUGGING)
                            return

                self._advance_pipeline(session, message)

        except (InvalidStateTransition, SessionTerminated) as e:
            logger.error(f"[ENGINE] State violation: {e}")

    def _advance_pipeline(self, session, message: TOONMessage):
        """
        Advance the session pipeline based on which agent just completed.
        """
        source = message.source.upper()

        if source == "PLANNER":
            if session.autonomy_mode == AutonomyMode.INTERACTIVE:
                session.transition(SessionState.AWAITING_APPROVAL)
            else:
                session.transition(SessionState.CODING)

        elif source == "CODER":
            session.transition(SessionState.REVIEWING)

        elif source == "REVIEWER":
            approved = message.payload.get("approved", False)
            if approved:
                session.transition(SessionState.COMPLETED)
                session.transition(SessionState.REFLECTING)
            else:
                session.transition(SessionState.DEBUGGING)

        elif source == "DEBUGGER":
            # Retry loop: debugger sends fix → back to coding
            session.transition(SessionState.CODING)

        elif source == "MEMORY_SCRIBE":
            # Reflecting is terminal — nothing to do.
            pass

    async def approve_session(self, trace_id: str):
        """
        Human approval gate. Called from WebSocket when user sends APPROVE.
        Transitions AWAITING_APPROVAL → CODING.
        """
        session = self.registry.get_session(trace_id)
        if not session:
            logger.error(f"[ENGINE] Cannot approve unknown session {trace_id}")
            return
        session.transition(SessionState.CODING)
        logger.info(f"[{trace_id}] Human approved. Advancing to CODING.")

    async def reject_session(self, trace_id: str, feedback: str = ""):
        """
        Human rejection gate. Transitions AWAITING_APPROVAL → PLANNING
        with user feedback injected.
        """
        session = self.registry.get_session(trace_id)
        if not session:
            return
        session.transition(SessionState.PLANNING)
        logger.info(f"[{trace_id}] Human rejected. Re-planning with feedback.")

    async def _watchdog_loop(self):
        """
        Periodic sweep of all active sessions, timing out any that exceeded TTL.
        """
        while True:
            try:
                timed_out = self.registry.run_watchdog_sweep()
                for tid in timed_out:
                    logger.critical(f"[WATCHDOG] Session {tid} timed out.")
                await asyncio.sleep(self._watchdog_interval)
            except asyncio.CancelledError:
                break
