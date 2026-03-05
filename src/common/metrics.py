import time
from contextlib import contextmanager

@contextmanager
def measure_latency(label: str, metrics: dict):
    start = time.perf_counter()
    yield
    metrics[label] = round(time.perf_counter() - start, 3)