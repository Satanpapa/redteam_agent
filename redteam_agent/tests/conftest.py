import sys
import types
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1] / "code"

pkg = types.ModuleType("rtcode")
pkg.__path__ = [str(CODE_DIR)]
sys.modules.setdefault("rtcode", pkg)
