import os
import difflib
import logging
from typing import List, Optional
from core.checkpoints import CheckpointManager

logger = logging.getLogger("nexus.tools.fsm")

class FSMTool:
    """
    File System Manager (FSM) Tool.
    The primary portal for agents to interact with the file system.
    Strictly enforces scoped path access and provides diff-based writes.
    """
    def __init__(self, workspace_root: str, checkpoint_manager: CheckpointManager):
        self.workspace_root = os.path.abspath(workspace_root)
        self.checkpoints = checkpoint_manager

    def _sanitize_path(self, path: str) -> str:
        """
        Ensures the requested path is within the workspace root.
        """
        abs_path = os.path.abspath(os.path.join(self.workspace_root, path))
        if not abs_path.startswith(self.workspace_root):
            raise PermissionError(f"Access denied: Path {path} is outside the workspace.")
        return abs_path

    def read_file(self, path: str) -> str:
        safe_path = self._sanitize_path(path)
        if not os.path.exists(safe_path):
            raise FileNotFoundError(f"File not found: {path}")
        
        with open(safe_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, path: str, content: str, trace_id: str):
        """
        Standard write: creates checkpoint first.
        """
        safe_path = self._sanitize_path(path)
        self.checkpoints.create_checkpoint(safe_path, trace_id)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"[FSM] Wrote file {path}")

    def apply_diff(self, path: str, diff_text: str, trace_id: str):
        """
        Applies a unified diff to a file after creating a checkpoint.
        Expects standard unified diff format (---, +++, @@, +, -, space).
        """
        safe_path = self._sanitize_path(path)
        self.checkpoints.create_checkpoint(safe_path, trace_id)

        if not os.path.exists(safe_path):
            raise FileNotFoundError(f"Cannot apply diff to non-existent file: {path}")

        with open(safe_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
            lines = original_content.splitlines(keepends=True)

        # Use difflib to apply the patch
        # Unified diffs usually start with headers. We'll strip them if present.
        diff_lines = diff_text.splitlines(keepends=True)
        
        # Basic check: if it looks like a unified diff
        headers_found = False
        for i, line in enumerate(diff_lines):
            if line.startswith("@@ "):
                # Start applying from the first hunk
                patch_to_apply = diff_lines[i:]
                headers_found = True
                break
        
        if not headers_found:
            raise ValueError("Invalid diff format: Could not find hunk header (@@)")

        # Python's difflib doesn't have a 'patch' tool, but we can reconstruct it.
        # For simplicity in v0.1, we'll use a direct replacement if the diff is small
        # OR we can use the 'patch' command if it's available on the system.
        # But per the USER's "Harness" rule, we want deterministic internal logic.
        
        try:
            patched_lines = self._manual_patch(lines, diff_text)
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.writelines(patched_lines)
            logger.info(f"[FSM] Applied diff to {path}")
        except Exception as e:
            logger.error(f"[FSM] Patching failed for {path}: {e}")
            raise

    def _manual_patch(self, original_lines: List[str], diff_text: str) -> List[str]:
        """
        Naive patcher for Unified Diff format.
        """
        import re
        diff_lines = diff_text.splitlines(keepends=True)
        result = []
        orig_cursor = 0
        
        hunk_header_re = re.compile(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@')
        
        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            match = hunk_header_re.match(line)
            if match:
                # Parse hunk header
                old_start = int(match.group(1)) - 1 # 1-indexed to 0-indexed
                old_len = int(match.group(2)) if match.group(2) else 1
                
                # Copy lines before the hunk
                while orig_cursor < old_start:
                    result.append(original_lines[orig_cursor])
                    orig_cursor += 1
                
                # Apply hunk instructions
                i += 1
                while i < len(diff_lines):
                    h_line = diff_lines[i]
                    if h_line.startswith('+'):
                        result.append(h_line[1:])
                    elif h_line.startswith('-'):
                        orig_cursor += 1
                    elif h_line.startswith(' '):
                        result.append(h_line[1:])
                        orig_cursor += 1
                    elif h_line.startswith('@@'):
                        break # Start of next hunk
                    else:
                        break # End of diff
                    i += 1
                continue
            i += 1
            
        # Copy remaining lines
        while orig_cursor < len(original_lines):
            result.append(original_lines[orig_cursor])
            orig_cursor += 1
            
        return result

    def list_tree(self, path: str = ".", depth: int = 3) -> List[str]:
        """
        Lists files in the workspace (read-only tree).
        """
        safe_base = self._sanitize_path(path)
        tree = []
        for root, dirs, files in os.walk(safe_base):
            # Calculate depth
            rel_root = os.path.relpath(root, safe_base)
            current_depth = 0 if rel_root == "." else len(rel_root.split(os.sep))
            if current_depth >= depth:
                continue
            
            for f in files:
                tree.append(os.path.join(rel_root, f))
        return tree
