import os
import sys
import pathlib

# Set required env vars before any import that reads them at module level
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1jaGFycyE=")

# Make lambda_consumers/ and lambda_consumers/ai_consumer/ importable
_ROOT = pathlib.Path(__file__).parent.parent.parent  # lambda_consumers/
_PKG = pathlib.Path(__file__).parent.parent           # lambda_consumers/ai_consumer/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
