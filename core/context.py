from typing import List, Dict
from core.token_ledger import TokenLedger

class ContextSegment:
    def __init__(self, content: str, priority: int, token_cost: int):
        self.content = content
        self.priority = priority # 1 (Critical) to 5 (Archive)
        self.token_cost = token_cost

class ContextManager:
    """
    Handles prompt assembly mapped to P1-P5 eviction bounds, facilitating the caching parameters.
    """
    def __init__(self, ledger: TokenLedger):
        self.ledger = ledger
        self.segments: List[ContextSegment] = []

    def inject_segment(self, segment: ContextSegment):
        self.segments.append(segment)
        self.ledger.add_usage(segment.token_cost)
        
    def assemble_prompt(self) -> str:
        """
        Assembles the active prompt based on eviction thresholds, ignoring dropped segments.
        This enables efficient 'Prompt Caching' mechanisms by maintaining static P1 prefixes.
        """
        # Sort by priority (P1 first)
        self.segments.sort(key=lambda x: x.priority)
        
        active_buffer = []
        for seg in self.segments:
            if not self.ledger.should_evict(seg.priority):
                active_buffer.append(seg.content)
            else:
                # Truncated or sent to vector store
                pass
                
        return "\n----------\n".join(active_buffer)
