import pytest
import os
import shutil
from tools.fsm import FSMTool
from core.checkpoints import CheckpointManager

@pytest.fixture
def fsm_env():
    # Setup test workspace
    base = "test_fsm_workspace"
    chk_dir = os.path.join(base, ".nexus/checkpoints")
    os.makedirs(base, exist_ok=True)
    os.makedirs(chk_dir, exist_ok=True)
    
    cm = CheckpointManager(chk_dir)
    fsm = FSMTool(base, cm)
    
    yield fsm, base
    
    # Cleanup
    shutil.rmtree(base)

def test_fsm_path_sanitization(fsm_env):
    fsm, base = fsm_env
    # Safe path
    assert fsm._sanitize_path("file.txt").endswith("file.txt")
    
    # Dangerous path
    with pytest.raises(PermissionError):
        fsm._sanitize_path("../outside.txt")

def test_fsm_write_and_checkpoint(fsm_env):
    fsm, base = fsm_env
    test_file = "hello.py"
    content = "print('hello')"
    
    # Write 1 (Initial)
    fsm.write_file(test_file, content, "trace_1")
    assert os.path.exists(os.path.join(base, test_file))
    
    # Write 2 (Should create checkpoint)
    new_content = "print('world')"
    fsm.write_file(test_file, new_content, "trace_1")
    
    # Check if checkpoint exists
    chk_files = os.listdir(os.path.join(base, ".nexus/checkpoints"))
    assert len(chk_files) == 1
    assert chk_files[0].startswith("trace_1")

def test_fsm_apply_diff(fsm_env):
    fsm, base = fsm_env
    test_file = "logic.py"
    original = "def foo():\n    return 1\n"
    fsm.write_file(test_file, original, "t2")
    
    # Unified diff to change 'return 1' to 'return 2'
    diff = """--- logic.py
+++ logic.py
@@ -1,2 +1,2 @@
 def foo():
-    return 1
+    return 2
"""
    fsm.apply_diff(test_file, diff, "t2")
    
    updated = fsm.read_file(test_file)
    assert "return 2" in updated
    assert "return 1" not in updated
