import re
import ast
import logging
from typing import Dict, Any, Optional
from schemas.messages import TOONMessage, MessageType

logger = logging.getLogger("nexus.core.guards")

class InputGuard:
    """
    Scans incoming user prompts or TOOL_RESULTs for dangerous patterns.
    Enforces Layer 1: Input Validation from SYSTEM_ARCHITECTURE.md.
    """
    # Simple regex for path traversal or suspicious shell patterns
    DANGEROUS_PATTERNS = [
        r"\.\./",              # Path traversal
        r"~/.*",               # Home directory access
        r"chmod\s\+",          # Permission changes
        r"rm\s-rf",            # Destructive deletes
        r"sudo\s",             # Privilege escalation
    ]

    @staticmethod
    def validate_input(text: str) -> bool:
        """
        Returns True if safe, False if a dangerous pattern is detected.
        """
        for pattern in InputGuard.DANGEROUS_PATTERNS:
            if re.search(pattern, text):
                logger.warning(f"[INPUT_GUARD] Blocked potentially dangerous input: {pattern}")
                return False
        return True

class OutputGuard:
    """
    Enforces Layer 4: Output Validation from SYSTEM_ARCHITECTURE.md.
    Validates agent outputs (Coder RESULTs) for syntax and safety.
    """
    
    @staticmethod
    def validate_code(code: str, language: str = "python") -> (bool, Optional[str]):
        """
        Checks for syntax errors and potential safety issues in generated code.
        """
        if not code.strip():
            return False, "Code is empty"

        if language == "python":
            try:
                ast.parse(code)
                return True, None
            except SyntaxError as e:
                return False, f"Syntax Error: {e.msg} at line {e.lineno}"
        
        # Add more languages as needed (JS/TS via Esprima/etc)
        return True, None

    @staticmethod
    def mask_secrets(text: str) -> str:
        """
        Layer 5: Secret Scrubbing. Redacts common API key patterns.
        """
        # Generic pattern for high-entropy strings or common keys
        key_patterns = [
            r"sk-[a-zA-Z0-9]{48}", # OpenAI
            r"ghp_[a-zA-Z0-9]{36}", # GitHub
        ]
        masked = text
        for pattern in key_patterns:
            masked = re.sub(pattern, "[REDACTED_API_KEY]", masked)
        return masked
