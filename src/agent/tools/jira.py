"""Jira tool - post investigation findings back to a Jira ticket."""

import json
import os

import boto3
import requests
from strands import tool

from common.logger import logger

REGION = os.environ["REGION_NAME"]
JIRA_SECRET_NAME = os.environ["JIRA_SECRET_NAME"]

_sm = boto3.client("secretsmanager", region_name=REGION)

# Module-level cache
_jira_creds: dict | None = None


def _get_jira_creds() -> dict:
    global _jira_creds
    if _jira_creds is None:
        _jira_creds = json.loads(_sm.get_secret_value(SecretId=JIRA_SECRET_NAME)["SecretString"])
    return _jira_creds


@tool
def post_jira_comment(issue_key: str, comment: str, email: str) -> str:
    """
    Post a comment on a Jira issue.

    Use this to report investigation findings, root cause analysis, or
    remediation recommendations back to the Jira ticket that triggered this alert.

    Args:
        issue_key: The Jira issue key (e.g. "SAM1-11").
        comment:   The comment text to post. Markdown is supported.
        email:     The actor's email address (passed as actorId in the request payload).

    Returns:
        Success message with comment URL, or an error description.
    """
    creds = _get_jira_creds()
    base_url = creds["base_url"].rstrip("/")
    api_token = creds["api_token"]

    url = f"{base_url}/rest/api/3/issue/{issue_key}/comment"
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": comment}],
                }
            ],
        }
    }

    resp = requests.post(
        url,
        json=payload,
        auth=(email, api_token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=10,
    )

    if resp.status_code == 201:
        comment_id = resp.json().get("id")
        comment_url = f"{base_url}/browse/{issue_key}?focusedCommentId={comment_id}"
        logger.info(f"[Jira] Comment posted: issue={issue_key} id={comment_id}")
        return f"Comment posted successfully: {comment_url}"

    logger.error(
        f"[Jira] Failed to post comment: issue={issue_key} status={resp.status_code} body={resp.text}"
    )
    return f"Failed to post comment: HTTP {resp.status_code} - {resp.text}"
