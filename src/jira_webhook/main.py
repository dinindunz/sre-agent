"""Jira webhook receiver Lambda.

API Gateway invokes this Lambda synchronously. The Lambda validates the
HMAC-SHA256 signature, verifies the triggering Jira user exists in Cognito,
builds a prompt from the Jira event, and calls the AgentCore HTTP endpoint
with stream=True (fire-and-forget) before returning 202 to Jira.
"""

import hashlib
import hmac
import json
import os
import urllib.parse
import uuid

import boto3
import requests

from common.logger import logger

REGION = os.environ["REGION_NAME"]
AGENT_RUNTIME_SSM_PARAM = os.environ["AGENT_RUNTIME_SSM_PARAM"]
AGENT_COGNITO_SECRET_NAME = os.environ["AGENT_COGNITO_SECRET_NAME"]
JIRA_SECRET_NAME = os.environ["JIRA_SECRET_NAME"]

_ssm = boto3.client("ssm", region_name=REGION)
_sm = boto3.client("secretsmanager", region_name=REGION)
_cognito = boto3.client("cognito-idp", region_name=REGION)

# Module-level cache - populated on cold start, reused across warm invocations
_agent_runtime_arn: str | None = None
_cognito_creds: dict | None = None


def _get_agent_runtime_arn() -> str:
    global _agent_runtime_arn
    if _agent_runtime_arn is None:
        _agent_runtime_arn = _ssm.get_parameter(Name=AGENT_RUNTIME_SSM_PARAM)["Parameter"]["Value"]
    return _agent_runtime_arn


def _get_cognito_creds() -> dict:
    global _cognito_creds
    if _cognito_creds is None:
        _cognito_creds = json.loads(
            _sm.get_secret_value(SecretId=AGENT_COGNITO_SECRET_NAME)["SecretString"]
        )
    return _cognito_creds


def _validate_signature(body: bytes, headers: dict) -> bool:
    """Validate Jira webhook HMAC-SHA256 signature.

    Jira sends the signature in X-Hub-Signature-256 as sha256=<hex>.
    Falls back to X-Hub-Signature for older Jira versions.
    """
    signature = headers.get("x-hub-signature-256") or headers.get("x-hub-signature", "")
    if not signature:
        logger.warning("Missing webhook signature header")
        return False

    jira_secret = _sm.get_secret_value(SecretId=JIRA_SECRET_NAME)["SecretString"]
    expected = "sha256=" + hmac.new(jira_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _verify_cognito_user(email: str) -> bool:
    """Check the email exists as an active user in the Cognito User Pool."""
    creds = _get_cognito_creds()
    user_pool_id = creds["user_pool_id"]
    resp = _cognito.list_users(
        UserPoolId=user_pool_id,
        Filter=f'email = "{email}"',
        Limit=1,
    )
    users = resp.get("Users", [])
    if not users:
        logger.warning(f"Cognito user not found for email={email}")
        return False
    if users[0].get("UserStatus") != "CONFIRMED":
        logger.warning(f"Cognito user not confirmed for email={email}")
        return False
    return True


def _get_access_token() -> str:
    """Obtain a Cognito OAuth2 access token via client credentials flow."""
    creds = _get_cognito_creds()
    resp = requests.post(
        creds["token_endpoint"],
        data={"grant_type": "client_credentials", "scope": "agent/invoke"},
        auth=(creds["client_id"], creds["client_secret"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _call_agentcore(jira_event: dict, actor_id: str) -> None:
    """Build a prompt from the Jira event and invoke the AgentCore HTTP endpoint."""
    runtime_arn = _get_agent_runtime_arn()
    encoded_arn = urllib.parse.quote(runtime_arn, safe="")
    endpoint = (
        f"https://bedrock-agentcore.{REGION}.amazonaws.com"
        f"/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    )

    event_type = jira_event.get("webhookEvent", "unknown")
    issue = jira_event.get("issue", {})
    issue_key = issue.get("key", "unknown")
    issue_summary = issue.get("fields", {}).get("summary", "")

    prompt = (
        f"Jira webhook event received: {event_type}. "
        f"Issue: {issue_key} - {issue_summary}. "
        f"Full event details: {json.dumps(jira_event)}"
    )

    token = _get_access_token()
    session_id = str(uuid.uuid4())

    # stream=True - wait only for response headers, not the full body.
    # AgentCore runs the LLM asynchronously; we confirm it accepted the request
    # and exit without blocking on the generated output.
    with requests.post(
        endpoint,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
        json={
            "input": {"value": prompt},
            "sessionId": session_id,
            "actorId": actor_id,
        },
        stream=True,
        timeout=30,
    ) as response:
        if response.status_code == 200:
            logger.info(f"AgentCore accepted request for issue {issue_key} actor={actor_id}")
        else:
            logger.error(
                f"AgentCore rejected request for issue {issue_key}: status={response.status_code}"
            )


def handler(event: dict, _context) -> dict:
    """Validate Jira webhook signature and forward the event to AgentCore."""
    # Normalise header keys to lowercase for consistent lookup
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body_str = event.get("body") or ""
    body_bytes = body_str.encode()

    if not _validate_signature(body_bytes, headers):
        logger.warning("Rejecting request: invalid Jira webhook signature")
        return {"statusCode": 401, "body": "Unauthorized"}

    try:
        jira_event = json.loads(body_str)
    except json.JSONDecodeError:
        logger.error("Invalid JSON body in Jira webhook")
        return {"statusCode": 400, "body": "Bad Request"}

    event_type = jira_event.get("webhookEvent", "unknown")
    issue_key = jira_event.get("issue", {}).get("key", "unknown")
    user = jira_event.get("user", {})
    user_id = user.get("accountId", "unknown")
    user_email = user.get("emailAddress", "")
    logger.info(
        f"Jira webhook received: event_type={event_type} issue_key={issue_key} "
        f"user_id={user_id} user_email={user_email}"
    )

    if not user_email:
        logger.warning("Rejecting request: no email in Jira webhook payload")
        return {"statusCode": 403, "body": "Forbidden"}

    if not _verify_cognito_user(user_email):
        logger.warning(f"Rejecting request: user not authorised email={user_email}")
        return {"statusCode": 403, "body": "Forbidden"}

    try:
        _call_agentcore(jira_event, actor_id=user_email)
    except Exception:
        logger.exception("Unhandled error calling AgentCore")

    return {"statusCode": 202, "body": "Accepted"}
