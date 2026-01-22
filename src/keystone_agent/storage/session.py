"""DynamoDB session backend for OpenAI Agents SDK."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

import aioboto3
from agents.memory import SessionABC
from botocore.exceptions import ClientError

from keystone_agent.config import settings


def _convert_floats(obj: Any) -> Any:
    """Recursively convert floats to Decimals for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_floats(item) for item in obj]
    elif hasattr(obj, "model_dump"):  # Pydantic models
        return _convert_floats(obj.model_dump())
    return obj


class DynamoDBSession(SessionABC):
    """
    DynamoDB-backed session for OpenAI Agents SDK.

    Stores conversation history in DynamoDB, enabling:
    - Multi-turn conversations within a board run
    - Persistent session state across restarts
    - Project history queries via GSI

    Table schema:
    - PK: session_id
    - GSI: project_id-created_at-index

    Attributes stored:
    - session_id, project_id, created_at
    - items (conversation history as JSON list)
    - metadata (mode, request_text, context, etc.)
    - final_output (board result)
    - rating, rating_notes
    """

    def __init__(
        self,
        session_id: str | None = None,
        project_id: str = "default",
        metadata: dict[str, Any] | None = None,
    ):
        """
        Initialize DynamoDB session.

        Args:
            session_id: Existing session ID to resume, or None to create new
            project_id: Project identifier for history queries
            metadata: Optional metadata (mode, request_text, etc.)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.project_id = project_id
        self.metadata = metadata or {}
        self._created = False

        self._boto_session = aioboto3.Session()
        self._client_kwargs: dict[str, Any] = {"region_name": settings.aws_region}

        if settings.dynamodb_endpoint_url:
            self._client_kwargs["endpoint_url"] = settings.dynamodb_endpoint_url

        self.table_name = settings.dynamodb_table_name

    def _now(self) -> str:
        """Get current UTC timestamp as ISO string."""
        return datetime.now(timezone.utc).isoformat()

    async def _ensure_created(self) -> None:
        """Ensure session exists in DynamoDB."""
        if self._created:
            return

        async with self._boto_session.resource("dynamodb", **self._client_kwargs) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            # Try to get existing session
            try:
                response = await table.get_item(Key={"session_id": self.session_id})
                if response.get("Item"):
                    self._created = True
                    return
            except ClientError:
                pass

            # Create new session
            item = _convert_floats({
                "session_id": self.session_id,
                "project_id": self.project_id,
                "created_at": self._now(),
                "items": [],  # Conversation history
                **self.metadata,
            })

            await table.put_item(Item=item)
            self._created = True

    async def get_items(self) -> list[dict[str, Any]]:
        """Get all conversation items from session."""
        await self._ensure_created()

        async with self._boto_session.resource("dynamodb", **self._client_kwargs) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.get_item(
                    Key={"session_id": self.session_id},
                    ProjectionExpression="items",
                )
                return response.get("Item", {}).get("items", [])
            except ClientError:
                return []

    async def add_items(self, items: list[dict[str, Any]]) -> None:
        """Add conversation items to session."""
        await self._ensure_created()

        # Filter out reasoning items - they can't be replayed with reasoning models
        filtered_items = [
            item for item in items
            if item.get("type") != "reasoning"
        ]

        if not filtered_items:
            return

        async with self._boto_session.resource("dynamodb", **self._client_kwargs) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            await table.update_item(
                Key={"session_id": self.session_id},
                UpdateExpression="SET #items = list_append(if_not_exists(#items, :empty), :new_items)",
                ExpressionAttributeNames={"#items": "items"},
                ExpressionAttributeValues={
                    ":new_items": _convert_floats(filtered_items),
                    ":empty": [],
                },
            )

    async def pop_item(self) -> dict[str, Any] | None:
        """Remove and return the last conversation item."""
        items = await self.get_items()
        if not items:
            return None

        last_item = items[-1]

        async with self._boto_session.resource("dynamodb", **self._client_kwargs) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            await table.update_item(
                Key={"session_id": self.session_id},
                UpdateExpression=f"REMOVE #items[{len(items) - 1}]",
                ExpressionAttributeNames={"#items": "items"},
            )

        return last_item

    async def clear_session(self) -> None:
        """Clear all conversation items from session."""
        async with self._boto_session.resource("dynamodb", **self._client_kwargs) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            await table.update_item(
                Key={"session_id": self.session_id},
                UpdateExpression="SET #items = :empty",
                ExpressionAttributeNames={"#items": "items"},
                ExpressionAttributeValues={":empty": []},
            )

    # Extended methods for Keystone-specific data

    async def save_final_output(self, output: dict[str, Any]) -> None:
        """Save final board output to session."""
        await self._ensure_created()

        async with self._boto_session.resource("dynamodb", **self._client_kwargs) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            await table.update_item(
                Key={"session_id": self.session_id},
                UpdateExpression="SET final_output = :output, completed_at = :now",
                ExpressionAttributeValues={
                    ":output": _convert_floats(output),
                    ":now": self._now(),
                },
            )

    async def save_rating(self, rating: str, notes: str | None = None) -> None:
        """Save user rating to session."""
        async with self._boto_session.resource("dynamodb", **self._client_kwargs) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            update_expr = "SET rating = :rating, rated_at = :now"
            expr_values: dict[str, Any] = {
                ":rating": rating,
                ":now": self._now(),
            }

            if notes:
                update_expr += ", rating_notes = :notes"
                expr_values[":notes"] = notes

            await table.update_item(
                Key={"session_id": self.session_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )

    async def get_session_data(self) -> dict[str, Any] | None:
        """Get full session data."""
        async with self._boto_session.resource("dynamodb", **self._client_kwargs) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.get_item(Key={"session_id": self.session_id})
                return response.get("Item")
            except ClientError:
                return None

    @staticmethod
    async def get_project_history(
        project_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Query recent sessions for a project."""
        boto_session = aioboto3.Session()
        client_kwargs: dict[str, Any] = {"region_name": settings.aws_region}

        if settings.dynamodb_endpoint_url:
            client_kwargs["endpoint_url"] = settings.dynamodb_endpoint_url

        table_name = settings.dynamodb_table_name

        async with boto_session.resource("dynamodb", **client_kwargs) as dynamodb:
            table = await dynamodb.Table(table_name)

            try:
                response = await table.query(
                    IndexName="project_id-created_at-index",
                    KeyConditionExpression="project_id = :pid",
                    ExpressionAttributeValues={":pid": project_id},
                    ScanIndexForward=False,  # Newest first
                    Limit=limit,
                )
            except ClientError:
                return []

            history = []
            for item in response.get("Items", []):
                final = item.get("final_output", {})
                history.append({
                    "session_id": item["session_id"],
                    "created_at": item["created_at"],
                    "request_summary": item.get("request_text", "")[:200],
                    "verdict": final.get("final_verdict"),
                    "summary": final.get("final_summary", ""),
                })

            return history
