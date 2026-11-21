"""Run the FastAPI server."""
import sys
import warnings
from pathlib import Path

# Suppress LangGraph's internal pending deprecation warning for JsonPlusSerializer.
# This warning originates inside langgraph.checkpoint.serde.jsonplus (library code)
# and will be resolved in a future LangGraph release.
warnings.filterwarnings(
    "ignore",
    message="The default value of `allowed_objects` will change",
    category=DeprecationWarning,
)

# Ensure the backend directory is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
