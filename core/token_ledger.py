import logging

logger = logging.getLogger("nexus.ledger")

class TokenLedger:
    """
    Tracks token budget consumption per session/agent to ensure we don't blow past context bounds.
    """
    def __init__(self, max_session_tokens: int = 120000):
        self.max_session_tokens = max_session_tokens
        self.used_session_tokens = 0
        
        # Hard allocations as defined in NexusPRD 2.1
        self.slot_budgets = {
            "SYSTEM_PERSONA": 300,
            "USER_GRAPH": 500,
            "HISTORY_COMPRESSED": 1200,
            "TOOL_RESULTS": 800,
            "TASK_INSTRUCTION": 400
        }
        
    def add_usage(self, token_count: int, slot: str = "GLOBAL"):
        self.used_session_tokens += token_count
        usage_pct = self.used_session_tokens / self.max_session_tokens
        
        if usage_pct >= 0.95:
            logger.critical(f"[LEDGER] Budget at 95% ({self.used_session_tokens}/{self.max_session_tokens})! Imminent eviction required.")
        elif usage_pct >= 0.80:
            logger.warning(f"[LEDGER] Budget at 80%. Aggressive semantic compression enabled.")
        elif usage_pct >= 0.60:
            logger.info(f"[LEDGER] Budget at 60%. Triggering P4 rolling summarization.")

    def slot_limit(self, slot_key: str) -> int:
        return self.slot_budgets.get(slot_key, 2000)  # Default fallback remainder loop

    def should_evict(self, priority: int) -> bool:
        """ Tells context manager if a priority band should be dropped. """
        pct = self.used_session_tokens / self.max_session_tokens
        if priority >= 5: return True  # Archive always evicts
        if priority >= 4 and pct >= 0.60: return True
        if priority >= 3 and pct >= 0.70: return True
        if priority >= 2 and pct >= 0.85: return True
        return False # P1 Critical never evicts
