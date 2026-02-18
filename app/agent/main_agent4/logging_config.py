"""
Logging configuration for the deterministic planner.

Sets up:
- Console handler (INFO level)
- File handler (logs/planner.log in project root, overwrites each run)
- Standardized log format
"""

import logging
import os
from pathlib import Path
from tabulate import tabulate


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging with console and file handlers.

    Args:
        log_level: Logging level (default INFO)

    Returns:
        Configured logger instance
    """
    # Create logs directory in project root (relative path)
    log_dir = Path(__file__).parent.parent.parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "planner.log"

    # Get or create logger
    logger = logging.getLogger("planner")
    logger.setLevel(log_level)

    # Clear existing handlers (for when setup_logging is called multiple times)
    logger.handlers.clear()

    # Format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (DEBUG - overwrites each run)
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# Create default logger instance
logger = setup_logging()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f"planner.{name}")


def print_worker_registry() -> None:
    """
    Print the worker registry in a formatted table.

    Shows all registered workers with their name, goal_type, description,
    preconditions, and outputs.
    """
    from app.agent.main_agent4.worker_registry import WORKER_REGISTRY

    if not WORKER_REGISTRY:
        print("No workers registered.")
        return

    headers = ["Name", "Type", "Description", "Preconditions", "Outputs"]
    rows = []
    for w in WORKER_REGISTRY:
        # Truncate long fields for display
        desc = w.get("description", "")[:50] + "..." if len(w.get("description", "")) > 50 else w.get("description", "")
        preconds = ", ".join(w.get("preconditions", []))
        outputs = ", ".join(w.get("outputs", []))

        rows.append([
            w.get("name", ""),
            w.get("goal_type", ""),
            desc,
            preconds[:40] + "..." if len(preconds) > 40 else preconds,
            outputs,
        ])

    print("\n" + "=" * 80)
    print("WORKER REGISTRY")
    print("=" * 80)
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print(f"\nTotal: {len(WORKER_REGISTRY)} workers registered")
    print("=" * 80 + "\n")
