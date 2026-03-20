#!/usr/bin/env python3
"""Create a user in the Cognito User Pool for testing actor_id mapping."""

import json
import os
import sys

import boto3
from dotenv import load_dotenv

load_dotenv()

REGION_NAME = os.environ.get("REGION_NAME")
STACK_PREFIX = os.environ.get("STACK_PREFIX", "sre-agent-stack-dev")


def create_user(
    user_name: str, email: str, user_pool_id: str, temp_password: str = "TempPass123!"
) -> None:
    """
    Create a user in Cognito User Pool.

    Creates a user with:
    - Email for authentication
    - preferred_username for easy lookup (this is what goes in .env as ACTOR_ID)
    - Auto-generated UUID as the actual Cognito username

    Args:
        user_name: Simple username (e.g., "actor-123") - used for preferred_username
        email: User's email address
        user_pool_id: Cognito User Pool ID
        temp_password: Temporary password (user will be auto-confirmed)
    """
    cognito = boto3.client("cognito-idp", region_name=REGION_NAME)

    try:
        # Check if user already exists by preferred_username
        response = cognito.list_users(
            UserPoolId=user_pool_id, Filter=f'preferred_username = "{user_name}"', Limit=1
        )

        if response.get("Users"):
            existing_user = response["Users"][0]
            print(f"✅ User with preferred_username '{user_name}' already exists")
            print(f"   Cognito Username: {existing_user['Username']}")
            attrs = {attr["Name"]: attr["Value"] for attr in existing_user.get("Attributes", [])}
            print(f"   Email: {attrs.get('email', 'N/A')}")
            print(f"   Preferred Username: {attrs.get('preferred_username', 'N/A')}")
            return

        print("Creating user...")

        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            TemporaryPassword=temp_password,
            MessageAction="SUPPRESS",
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "preferred_username", "Value": user_name},
            ],
        )

        # Set permanent password (auto-confirm)
        cognito.admin_set_user_password(
            UserPoolId=user_pool_id, Username=email, Password=temp_password, Permanent=True
        )

        response = cognito.admin_get_user(UserPoolId=user_pool_id, Username=email)

        print("✅ User created successfully")
        print(f"   Preferred Username: {user_name} ← Use this in .env as ACTOR_ID")
        print(f"   Email: {email}")
        print(f"   Cognito Username: {response['Username']}")

    except Exception as e:
        print(f"❌ Error creating user: {e}")
        sys.exit(1)


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_user.py <user_name> [password]")
        print()
        print("Example:")
        print("  python scripts/create_user.py actor-123")
        print()
        print("Notes:")
        print("  - Email domain is read from .env USER_DOMAIN variable")
        print("  - The user_name is what you'll use in .env as ACTOR_ID")
        sys.exit(1)

    user_name = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else "TempPass123!"

    user_domain = os.environ.get("USER_DOMAIN", "example.com")
    email = f"{user_name}@{user_domain}"

    # Get User Pool ID from Secrets Manager
    sm = boto3.client("secretsmanager", region_name=REGION_NAME)
    secret = json.loads(
        sm.get_secret_value(SecretId=f"{STACK_PREFIX}/agent-cognito")["SecretString"]
    )
    user_pool_id = secret["user_pool_id"]

    print(f"Stack Prefix: {STACK_PREFIX}")
    print(f"User Pool ID: {user_pool_id}")
    print(f"Email: {email}\n")

    create_user(user_name, email, user_pool_id, password)


if __name__ == "__main__":
    main()
