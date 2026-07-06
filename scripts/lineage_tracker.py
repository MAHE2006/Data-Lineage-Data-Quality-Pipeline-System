"""
lineage_tracker.py
-------------------
A lightweight, dependency-free data lineage logger.

Every pipeline stage calls `LineageTracker.log_stage(...)` after it runs.
Each call appends one JSON record to metadata/lineage_log.json describing:
    - which stage ran
    - source -> target (the data flow edge)
    - row counts in/out (so row loss is visible)
    - columns touched
    - transformation description
    - timestamp + run_id (so multiple pipeline runs don't overwrite history)

This is the "full data lineage visibility" component of the project:
at any point you can answer "where did this table come from, what
happened to it, and how many rows were dropped/changed at each step?"
"""

import json
import os
import uuid
from datetime import datetime, timezone


class LineageTracker:
    def __init__(self, log_path="metadata/lineage_log.json", run_id=None):
        self.log_path = log_path
        self.run_id = run_id or str(uuid.uuid4())[:8]
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w") as f:
                json.dump([], f)

    def log_stage(
        self,
        stage_name,
        source,
        target,
        rows_in,
        rows_out,
        columns=None,
        transformation="",
        extra=None,
    ):
        record = {
            "run_id": self.run_id,
            "stage": stage_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "target": target,
            "rows_in": rows_in,
            "rows_out": rows_out,
            "rows_dropped": rows_in - rows_out,
            "columns": columns or [],
            "transformation": transformation,
            "extra": extra or {},
        }

        with open(self.log_path, "r") as f:
            history = json.load(f)
        history.append(record)
        with open(self.log_path, "w") as f:
            json.dump(history, f, indent=2)

        print(
            f"[LINEAGE] {stage_name}: {source} -> {target} "
            f"| rows {rows_in} -> {rows_out} "
            f"(dropped {rows_in - rows_out})"
        )
        return record

    @staticmethod
    def read_log(log_path="metadata/lineage_log.json"):
        with open(log_path, "r") as f:
            return json.load(f)
