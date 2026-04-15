import os
import shutil
import time
import logging
from typing import Optional

logger = logging.getLogger("nexus.core.checkpoints")

class CheckpointManager:
    """
    Manages physical file backups for every write operation.
    Enforces Layer 5 Checkpoint Before Mutate principle.
    """
    def __init__(self, base_dir: str = ".nexus/checkpoints"):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir, exist_ok=True)

    def create_checkpoint(self, file_path: str, trace_id: str) -> Optional[str]:
        """
        Creates a timestamped backup of the file before it is modified.
        Returns the path to the backup file.
        """
        if not os.path.exists(file_path):
            return None # New file, no checkpoint needed for rollback

        try:
            filename = os.path.basename(file_path)
            timestamp = int(time.time())
            backup_name = f"{trace_id}_{timestamp}_{filename}.bak"
            backup_path = os.path.join(self.base_dir, backup_name)
            
            shutil.copy2(file_path, backup_path)
            logger.info(f"[CHECKPOINT] Created backup for {file_path} at {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"[CHECKPOINT] Failed to create backup for {file_path}: {e}")
            return None

    def restore_checkpoint(self, backup_path: str, target_path: str):
        """
        Restores a file from a checkpoint.
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Checkpoint {backup_path} not found.")
            
        shutil.copy2(backup_path, target_path)
        logger.warning(f"[CHECKPOINT] Restored {target_path} from {backup_path}")
