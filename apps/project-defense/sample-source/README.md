# Durable Review Queue

This sample project records review jobs in SQLite before a worker claims them. It demonstrates restart recovery but does not contain production latency, throughput, p95, or p99 measurements.

`queue.py` owns the state transition invariant. A claimed job may be reclaimed after its lease expires.
