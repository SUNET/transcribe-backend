import collections
import time


class HealthStatus:
    """
    Health status tracking for workers.
    Stores load average, memory usage, GPU usage, and last seen timestamp for each worker.
    """

    def __init__(self):
        """
        Initialize the HealthStatus with an empty dictionary of workers.
        """
        self.workers = {}

    def add(self, data):
        """
        Add a new health status entry for a worker.

        Parameters:
            data (dict): A dictionary containing worker_id, load_avg, memory_usage, and gpu_usage.
        """
        worker_id = data.get("worker_id")
        worker_load_avg = data.get("load_avg", 0)
        worker_memory_usage = data.get("memory_usage", 0)
        worker_gpu_usage = data.get("gpu_usage", 0)
        worker_seen = time.time()

        if worker_id not in self.workers:
            self.workers[worker_id] = collections.deque(maxlen=300)

        self.workers[worker_id].append(
            {
                "load_avg": worker_load_avg,
                "memory_usage": worker_memory_usage,
                "gpu_usage": worker_gpu_usage,
                "seen": worker_seen,
            }
        )

    def get(self):
        """
        Get the health status of all workers.
        Returns:
            dict: A dictionary containing the health status of all workers.
        """
        result = {}

        workers = dict(sorted(self.workers.items()))

        for worker_id, stats in workers.items():
            result[worker_id] = []
            for stat in stats:
                result[worker_id].append(stat)

        return result
