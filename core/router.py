import re
from typing import Dict, Any

class BaseRouter:
    """
    Classifies incoming user tasks into sub-agent queues using trigger patterns.
    """
    def __init__(self):
        # Basic mapping extracted from YAML manifests earlier
        self.routes = [
            (r"^(plan|architect|design|break down).*", "PLANNER"),
            (r"^(write|generate|implement|create).*", "CODER"),
            (r"^(review|check|validate|analyze).*", "REVIEWER"),
            (r"^(debug|fix|trace|resolve).*", "DEBUGGER"),
            (r"^(research|find|search|scrape).*", "RESEARCHER")
        ]

    def classify_task(self, prompt: str) -> str:
        """
        Iterates over prioritized regex routes. Fallback directly to PLANNER if ambiguous.
        """
        prompt_lower = prompt.lower().strip()
        for pattern, target in self.routes:
            if re.match(pattern, prompt_lower):
                return target
        
        # Default safety fallback
        return "PLANNER"
