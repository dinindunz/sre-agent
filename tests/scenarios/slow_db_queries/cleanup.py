"""Delete CloudWatch log groups created by inject.py.

Usage:
    python tests/scenarios/slow_db_queries/cleanup.py
    python tests/scenarios/slow_db_queries/cleanup.py --dry-run
"""

import argparse
import os

import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.environ.get("REGION_NAME", "ap-southeast-2")
LOG_GROUP_PREFIX = "/production"

_logs = boto3.client("logs", region_name=REGION)


def cleanup(dry_run: bool = False) -> None:
    paginator = _logs.get_paginator("describe_log_groups")
    groups = []
    for page in paginator.paginate(logGroupNamePrefix=LOG_GROUP_PREFIX):
        groups.extend(g["logGroupName"] for g in page["logGroups"])

    if not groups:
        print(f"No log groups found under {LOG_GROUP_PREFIX}")
        return

    for group in groups:
        if dry_run:
            print(f"[dry-run] would delete: {group}")
        else:
            _logs.delete_log_group(logGroupName=group)
            print(f"Deleted: {group}")

    print(f"\n{'Would delete' if dry_run else 'Deleted'} {len(groups)} log group(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete production log groups")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without calling AWS")
    args = parser.parse_args()
    cleanup(dry_run=args.dry_run)
