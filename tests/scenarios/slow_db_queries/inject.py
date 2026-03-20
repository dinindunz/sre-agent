"""Inject scenario logs into CloudWatch.

Reads the .jsonl files in logs/ and pushes each service's entries into its
own CloudWatch log group under /production/<service>.

Timestamps are anchored to (now - 10 minutes) + offset_seconds so the logs
appear as a recent incident in CloudWatch. Logs Insights queries have a
60-minute lookback - inject immediately before triggering the Jira alert.

Also updates the Triggered timestamp in jira.md to the current UTC time.

Usage:
    python tests/scenarios/slow_db_queries/inject.py
    python tests/scenarios/slow_db_queries/inject.py --dry-run
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from dotenv import load_dotenv
import os

load_dotenv()

REGION = os.environ.get("REGION_NAME", "ap-southeast-2")
LOG_GROUP_PREFIX = "/production"
LOGS_DIR = Path(__file__).parent / "logs"
JIRA_MD = Path(__file__).parent / "jira.md"

_logs = boto3.client("logs", region_name=REGION)


def _ensure_log_group(group: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would create log group: {group}")
        return
    try:
        _logs.create_log_group(logGroupName=group)
        print(f"  Created log group: {group}")
    except _logs.exceptions.ResourceAlreadyExistsException:
        print(f"  Log group exists: {group}")


def _ensure_log_stream(group: str, stream: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would create log stream: {stream}")
        return
    try:
        _logs.create_log_stream(logGroupName=group, logStreamName=stream)
    except _logs.exceptions.ResourceAlreadyExistsException:
        pass


def _put_events(group: str, stream: str, events: list[dict], dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would put {len(events)} events to {group}/{stream}")
        return

    # CloudWatch requires events sorted by timestamp
    events_sorted = sorted(events, key=lambda e: e["timestamp"])

    # PutLogEvents limit: 10,000 events or 1MB per batch
    batch_size = 500
    for i in range(0, len(events_sorted), batch_size):
        batch = events_sorted[i : i + batch_size]
        _logs.put_log_events(
            logGroupName=group,
            logStreamName=stream,
            logEvents=batch,
        )
        print(f"  Pushed {len(batch)} events to {group}/{stream}")


def inject(dry_run: bool = False) -> None:
    # Anchor: incident started 10 minutes ago
    anchor_ms = int((time.time() - 600) * 1000)
    stream_name = datetime.now(timezone.utc).strftime("%Y/%m/%d/inject-%H%M%S")

    for jsonl_file in sorted(LOGS_DIR.glob("*.jsonl")):
        service = jsonl_file.stem  # e.g. "api-service"
        log_group = f"{LOG_GROUP_PREFIX}/{service}"

        print(f"\nProcessing {service}...")
        _ensure_log_group(log_group, dry_run)
        _ensure_log_stream(log_group, stream_name, dry_run)

        events = []
        with jsonl_file.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                offset_ms = entry.pop("offset_seconds", 0) * 1000
                message = json.dumps(entry)
                events.append({"timestamp": anchor_ms + offset_ms, "message": message})

        _put_events(log_group, stream_name, events, dry_run)

    _update_jira_timestamp(dry_run)

    print("\nDone.")
    if not dry_run:
        print(f"Stream name: {stream_name}")


def _update_jira_timestamp(dry_run: bool) -> None:
    triggered = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    original = JIRA_MD.read_text()
    updated = re.sub(r"Triggered:.*", f"Triggered: {triggered}", original)
    if dry_run:
        print(f"\n  [dry-run] would update jira.md Triggered: {triggered}")
        return
    JIRA_MD.write_text(updated)
    print(f"\nUpdated jira.md: Triggered: {triggered}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject slow-db-queries scenario into CloudWatch")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without calling AWS")
    args = parser.parse_args()
    inject(dry_run=args.dry_run)
