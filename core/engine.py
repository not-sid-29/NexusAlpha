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
from bus.protocol import create_message, create_task_message
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
from memory.db_manager import DatabaseManager

logger = logging.getLogger("nexus.engine")


class NexusEngine:
    """
    The Orchestration brain. Manages session lifecycles via FSM,
    hooks the WebSocket interface to the TOON bus, and runs a periodic
    watchdog to kill stalled sessions.
    """

    def __init__(self, dispatcher: AsyncDispatcher, db_manager: Optional[DatabaseManager] = None):
        self.dispatcher = dispatcher
        self.db = db_manager
        self.router = BaseRouter()
        self.registry = SessionRegistry()
        self.event_callback = None  # Hook for API layer to send WS updates
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_interval = 10.0  # seconds between sweeps

    async def start(self):
        """Start the watchdog background task and subscribe to the bus."""
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        
        # BUG FIX: Engine must listen for agent results targeted at 'ENGINE'
        await self.dispatcher.subscribe("ENGINE", self.handle_agent_result)
        
        logger.info("[ENGINE] Watchdog started and subscribed to ENGINE bus.")

    async def shutdown(self):
        """Graceful shutdown: cancel watchdog."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        logger.info("[ENGINE] Shutdown complete.")

    async def _emit_session_update(self, session, event_type="state_update", payload=None):
        """Bridge to the API layer via callback."""
        if self.event_callback:
            data = {
                "event": event_type,
                "trace_id": session.trace_id,
                "state": session.state.value,
                "payload": payload or {}
            }
            await self.event_callback(session.trace_id, data)

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
        session.user_prompt = user_prompt
        session.user_id = client_id or "local_user"
        await self._persist_session(session)

        # Transition: PENDING → ROUTING
        session.transition(SessionState.ROUTING)
        await self._persist_session(session)
        
        # ENTRYPOINT: All high-level tasks start at the PLANNER for decomposition
        target_agent = "PLANNER"

        # Transition: ROUTING → PLANNING
        session.transition(SessionState.PLANNING)
        await self._persist_session(session)
        await self._emit_session_update(session)

        logger.info(
            f"[{trace_id}] Engine routing task to {target_agent} (ENTRYPOINT) "
            f"(mode={autonomy_mode.value})"
        )

        msg = create_task_message(
            source="ENGINE",
            target=target_agent,
            payload_data={"instruction": user_prompt, "user_id": session.user_id},
            trace_id=trace_id,
        )
        await self._persist_toon_message(msg)
        await self.dispatcher.publish(msg)
        return trace_id

    async def handle_agent_result(self, message: TOONMessage):
        """
        Callback invoked when an agent publishes a RESULT or ERROR back
        to the bus. Drives the session FSM forward.
        """
        logger.info(f"[{message.trace_id}] Engine heard {message.msg_type.value} from {message.source}")
        session = self.registry.get_session(message.trace_id)
        if not session:
            logger.error(f"[ENGINE] No session for trace_id={message.trace_id}")
            return

        try:
            await self._persist_toon_message(message)
            if message.msg_type == MessageType.ERROR:
                if session.state == SessionState.CODING:
                    session.transition(SessionState.REVIEWING)
                    session.transition(SessionState.DEBUGGING)
                elif session.state == SessionState.DEBUGGING:
                    # Retry → back to coding (counter enforced inside FSM)
                    session.transition(SessionState.CODING)
                else:
                    session.transition(SessionState.FAILED)
                await self._persist_session(session)
                await self._emit_session_update(session, "agent_error", message.payload)

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
                            await self._persist_session(session)
                            await self._emit_session_update(session, "validation_error", {"error": err})
                            return

                await self._advance_pipeline(session, message)
                await self._persist_session(session)
                # Emit the result AND the new state
                await self._emit_session_update(session, "agent_result", {
                    "source": message.source,
                    "payload": message.payload
                })
                if session.state == SessionState.REFLECTING:
                    await self._emit_reflection(session)

        except (InvalidStateTransition, SessionTerminated) as e:
            logger.error(f"[ENGINE] State violation: {e}")

    async def _trigger_next_agent(self, session):
        """Based on current session state, publish the next task to the bus."""
        target = None
        payload = {}

        if session.state == SessionState.PLANNING:
            target = "PLANNER"
            payload = {"instruction": session.user_prompt}
        elif session.state == SessionState.CODING:
            target = "CODER"
            # Extract last plan from history if it exists
            # For now, we pass the original prompt, but in Phase 4 we'll pass the plan
            payload = {"instruction": session.user_prompt}
        elif session.state == SessionState.DEBUGGING:
            target = "DEBUGGER"
            # Get the last error or failing result from history
            # For now, we use a placeholder or the last session error
            payload = {
                "instruction": session.user_prompt,
                "error": "The previous code generation failed or produced invalid output."
            }

        if target:
            msg = create_task_message(
                source="ENGINE",
                target=target,
                payload_data={**payload, "user_id": getattr(session, "user_id", "local_user")},
                trace_id=session.trace_id
            )
            await self._persist_toon_message(msg)
            await self.dispatcher.publish(msg)
            logger.info(f"[{session.trace_id}] Triggered {target} for state {session.state.value}")

    async def _advance_pipeline(self, session, message: TOONMessage):
        """
        Advance the session pipeline based on which agent just completed.
        """
        source = message.source.upper()

        if source == "PLANNER":
            if session.autonomy_mode == AutonomyMode.INTERACTIVE:
                session.transition(SessionState.AWAITING_APPROVAL)
            else:
                session.transition(SessionState.CODING)
                await self._trigger_next_agent(session)

        elif source == "CODER":
            session.transition(SessionState.REVIEWING)
            # Future: Trigger REVIEWER here

        elif source == "REVIEWER":
            approved = message.payload.get("approved", False)
            if approved:
                session.transition(SessionState.COMPLETED)
                session.transition(SessionState.REFLECTING)
            else:
                session.transition(SessionState.DEBUGGING)
                await self._trigger_next_agent(session)

        elif source == "DEBUGGER":
            # Retry loop: debugger sends fix → back to coding
            session.transition(SessionState.CODING)
            await self._trigger_next_agent(session)

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
        await self._persist_session(session)
        await self._emit_session_update(session)
        await self._trigger_next_agent(session)
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
        await self._persist_session(session)
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
                    session = self.registry.get_session(tid)
                    if session:
                        await self._persist_session(session)
                await asyncio.sleep(self._watchdog_interval)
            except asyncio.CancelledError:
                break

    async def _persist_session(self, session) -> None:
        if not self.db:
            return
        user_id = getattr(session, "user_id", "local_user")
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id, user_id),
            )
            conn.execute(
                """
                INSERT INTO sessions (trace_id, user_id, status, autonomy_mode)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    status = excluded.status,
                    autonomy_mode = excluded.autonomy_mode,
                    end_time = CASE
                        WHEN excluded.status IN ('REFLECTING', 'TIMED_OUT') THEN NOW()
                        ELSE sessions.end_time
                    END
                """,
                (
                    session.trace_id,
                    user_id,
                    session.state.value,
                    session.autonomy_mode.value,
                ),
            )
            conn.commit()

    async def _persist_toon_message(self, message: TOONMessage) -> None:
        if not self.db:
            return
        if message.msg_type == MessageType.MEMORY_WRITE:
            return
        write_msg = create_message(
            msg_type=MessageType.MEMORY_WRITE,
            source="ENGINE",
            target="MEMORY_SCRIBE",
            payload={
                "msg_type": message.msg_type.value,
                "source": message.source,
                "target": message.target,
                "payload": message.payload,
            },
            trace_id=message.trace_id,
        )
        await self.dispatcher.publish(write_msg)

    async def _emit_reflection(self, session) -> None:
        reflection_msg = create_message(
            msg_type=MessageType.REFLECTION,
            source="ENGINE",
            target="MEMORY_SCRIBE",
            payload={"user_id": getattr(session, "user_id", "local_user")},
            trace_id=session.trace_id,
        )
        await self.dispatcher.publish(reflection_msg)
