"""CloudWatch Logs tools - discover log groups and run Logs Insights queries."""

import os
import time

import boto3
from strands import tool

from common.logger import logger

REGION = os.environ["REGION_NAME"]
_logs = boto3.client("logs", region_name=REGION)


@tool
def list_log_groups(prefix: str = "") -> list[str]:
    """
    List CloudWatch log group names, optionally filtered by a prefix.

    Use this to discover what log groups exist before querying them.

    Args:
        prefix: Optional prefix to filter log groups (e.g. "/production").
                Returns all log groups if empty.

    Returns:
        List of log group names.
    """
    kwargs = {}
    if prefix:
        kwargs["logGroupNamePrefix"] = prefix

    groups = []
    paginator = _logs.get_paginator("describe_log_groups")
    for page in paginator.paginate(**kwargs):
        groups.extend(g["logGroupName"] for g in page["logGroups"])

    logger.info(f"[CloudWatch] Listed {len(groups)} log groups prefix='{prefix}'")
    return groups


@tool
def query_logs(
    log_group_names: list[str],
    query: str,
    lookback_minutes: int = 60,
    limit: int = 50,
) -> list[dict]:
    """
    Run a CloudWatch Logs Insights query across one or more log groups.

    Use this to search and filter log entries. Logs Insights query syntax examples:
      - fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc
      - fields @timestamp, level, message | filter level = "ERROR" | stats count() by bin(5m)
      - fields @timestamp, @message | filter @message like /timeout/ | sort @timestamp asc

    Args:
        log_group_names: List of log group names to query.
        query:           CloudWatch Logs Insights query string.
        lookback_minutes: How far back to search (default: 60 minutes).
        limit:           Maximum number of results to return (default: 50, max: 10000).

    Returns:
        List of result rows, each row is a dict of field name to value.
    """
    end_time = int(time.time() * 1000)
    start_time = end_time - (lookback_minutes * 60 * 1000)

    response = _logs.start_query(
        logGroupNames=log_group_names,
        startTime=start_time,
        endTime=end_time,
        queryString=query,
        limit=limit,
    )
    query_id = response["queryId"]
    logger.info(f"[CloudWatch] Query started: id={query_id} groups={log_group_names}")

    # Poll until complete (timeout after 60 seconds)
    timeout = time.time() + 60
    while time.time() < timeout:
        result = _logs.get_query_results(queryId=query_id)
        status = result["status"]
        if status == "Complete":
            rows = [{field["field"]: field["value"] for field in row} for row in result["results"]]
            logger.info(f"[CloudWatch] Query complete: id={query_id} rows={len(rows)}")
            return rows
        if status in ("Failed", "Cancelled"):
            logger.error(f"[CloudWatch] Query {status}: id={query_id}")
            return []
        time.sleep(2)

    logger.warning(f"[CloudWatch] Query timed out: id={query_id}")
    return []
