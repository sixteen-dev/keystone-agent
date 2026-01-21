#!/usr/bin/env python3
"""Create DynamoDB table for Keystone Agent.

Single-table design backing the OpenAI Agents SDK SessionABC implementation.
Stores conversation history, metadata, final outputs, and ratings.

Usage:
    # For local development (LocalStack or DynamoDB Local)
    python scripts/create_dynamodb_tables.py --local

    # For AWS (uses your configured credentials)
    python scripts/create_dynamodb_tables.py

    # With custom prefix
    python scripts/create_dynamodb_tables.py --prefix myapp_

    # Specify region
    python scripts/create_dynamodb_tables.py --region us-west-2
"""

import argparse
import sys

import boto3
from botocore.exceptions import ClientError


def create_table(
    endpoint_url: str | None = None,
    region: str = "us-east-2",
    prefix: str = "keystone_",
) -> None:
    """Create the sessions table with GSI for project queries."""

    if endpoint_url:
        dynamodb = boto3.client(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id="dummy",
            aws_secret_access_key="dummy",
        )
    else:
        dynamodb = boto3.client("dynamodb", region_name=region)

    table_name = f"{prefix}sessions_dev"

    table_def = {
        "TableName": table_name,
        "KeySchema": [
            {"AttributeName": "session_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "project_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "project_id-created_at-index",
                "KeySchema": [
                    {"AttributeName": "project_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }

    try:
        dynamodb.create_table(**table_def)
        print(f"✓ Created table: {table_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"○ Table already exists: {table_name}")
        else:
            print(f"✗ Failed to create {table_name}: {e}")
            sys.exit(1)

    print(f"\nTable created with prefix '{prefix}'")
    print("\nSchema:")
    print("  PK: session_id (UUID)")
    print("  GSI: project_id-created_at-index")
    print("\nAttributes stored per session:")
    print("  - session_id, project_id, created_at")
    print("  - items (SDK conversation history)")
    print("  - mode, request_text, option_a, option_b, since_days (metadata)")
    print("  - final_output (board result JSON)")
    print("  - completed_at")
    print("  - rating, rating_notes, rated_at")
    print("\nSet these environment variables:")
    print(f"  export KEYSTONE_DYNAMODB_TABLE_PREFIX={prefix}")
    if endpoint_url:
        print(f"  export KEYSTONE_DYNAMODB_ENDPOINT_URL={endpoint_url}")


def main():
    parser = argparse.ArgumentParser(description="Create DynamoDB table for Keystone Agent")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local DynamoDB (localhost:8000)",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=None,
        help="Custom DynamoDB endpoint URL",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-2",
        help="AWS region (default: us-east-2)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="keystone_",
        help="Table name prefix (default: keystone_)",
    )

    args = parser.parse_args()

    endpoint_url = args.endpoint
    if args.local and not endpoint_url:
        endpoint_url = "http://localhost:8000"

    print("Creating DynamoDB table...")
    if endpoint_url:
        print(f"Endpoint: {endpoint_url}")
    print(f"Region: {args.region}")
    print(f"Prefix: {args.prefix}")
    print()

    create_table(
        endpoint_url=endpoint_url,
        region=args.region,
        prefix=args.prefix,
    )


if __name__ == "__main__":
    main()
