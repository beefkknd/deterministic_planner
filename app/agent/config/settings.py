"""
Configuration for Deterministic Planner.

Loads settings from environment variables with defaults for local development.
"""

import os


# =============================================================================
# LLM Configuration
# =============================================================================

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local")  # "local" or "anthropic"

# Local model (LM Studio)
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3-8b")
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:1234/v1")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "dummy")  # LM Studio doesn't need real key

# Anthropic cloud model
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # Must be set if using Anthropic


# =============================================================================
# Test Configuration
# =============================================================================

# Sentence transformer model for semantic similarity
SENTENCE_TRANSFORMER_MODEL = os.getenv(
    "SENTENCE_TRANSFORMER_MODEL",
    "all-MiniLM-L6-v2"
)

# Similarity threshold for integration tests (0.0 - 1.0)
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))


# =============================================================================
# Helpers
# =============================================================================

def get_model_config() -> dict:
    """
    Get the current model configuration.

    Returns:
        Dict with provider, model name, and other settings
    """
    if LLM_PROVIDER == "local":
        return {
            "provider": "local",
            "model": LOCAL_MODEL,
            "base_url": LOCAL_BASE_URL,
            "api_key": LOCAL_API_KEY,
        }
    else:
        return {
            "provider": "anthropic",
            "model": ANTHROPIC_MODEL,
            "api_key": ANTHROPIC_API_KEY,
        }


def is_local() -> bool:
    """Check if using local model."""
    return LLM_PROVIDER == "local"


def is_cloud() -> bool:
    """Check if using cloud model."""
    return LLM_PROVIDER == "anthropic"
