"""
Node Infrastructure

Base worker classes and utilities.
"""


# =============================================================================
# Base Worker Class
# =============================================================================

class BaseWorker:
    """
    Base class for worker nodes.

    All workers should inherit from this class and implement ainvoke.
    """

    def __init__(self, name: str):
        """
        Initialize base worker.

        Args:
            name: Worker name
        """
        self.name = name

    async def ainvoke(self, worker_input: dict) -> dict:
        """
        Execute the worker asynchronously.

        Args:
            worker_input: WorkerInput dict with sub_goal and resolved_inputs

        Returns:
            WorkerResult dict
        """
        raise NotImplementedError("Subclasses must implement ainvoke")
