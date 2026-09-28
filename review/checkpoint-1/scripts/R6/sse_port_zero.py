import sys
sys.path.insert(0, "src")
from gmst.config import _merge, Config
try:
    cfg = _merge(Config(), {"sse_port": 0})
    print("OK", cfg.sse_port)
except Exception as e:
    print("FAIL:", type(e).__name__, e)
