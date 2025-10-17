import collections
import time


class HealthStatus:
    def __init__(self):
        self.workers = {}

    def add(self, data):
        worker_id = data.get("worker_id")
        worker_load_avg = data.get("load_avg", 0)
        worker_memory_usage = data.get("memory_usage", 0)
        worker_gpu_usage = data.get("gpu_usage", 0)
        worker_seen = time.time()

        if worker_id not in self.workers:
            self.workers[worker_id] = collections.deque(maxlen=600)

        self.workers[worker_id].append(
            {
                "load_avg": worker_load_avg,
                "memory_usage": worker_memory_usage,
                "gpu_usage": worker_gpu_usage,
                "seen": worker_seen,
            }
        )

    def get(self):
        result = {}

        for worker_id, stats in self.workers.items():
            result[worker_id] = []
            for stat in stats:
                result[worker_id].append(stat)

        return result
