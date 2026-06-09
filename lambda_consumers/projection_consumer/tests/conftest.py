import os
import sys
import pathlib

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

_ROOT = pathlib.Path(__file__).parent.parent.parent  # lambda_consumers/
_PKG = pathlib.Path(__file__).parent.parent           # lambda_consumers/projection_consumer/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
