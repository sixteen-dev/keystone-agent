"""Configuration management for Keystone Agent."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="KEYSTONE_",
        case_sensitive=False,
    )

    # Models (OpenAI API key read directly from OPENAI_API_KEY env var by SDK)
    orchestrator_model: str = "gpt-5-mini"
    specialist_model: str = "gpt-5-nano"

    # DynamoDB
    aws_region: str = "us-east-2"
    dynamodb_table_name: str = "keystone_sessions_dev"
    dynamodb_endpoint_url: str | None = None  # For local dev (e.g., http://localhost:8000)

    # Retry configuration
    max_retries: int = 1
    retry_delay: float = 0.5

    # Token limits (guidelines, not hard caps)
    specialist_max_tokens: int = 350
    final_max_tokens: int = 700

    # Context injection
    history_limit: int = 5


# Agent codenames mapping
AGENT_CODENAMES = {
    "product_operator": "Lynx",
    "growth_distribution": "Wildfire",
    "systems_architecture": "Bedrock",
    "capital_allocator": "Leverage",
    "risk_reality": "Sentinel",
    "creative_director": "Prism",
    "product_purist": "Razor",
    "orchestrator": "Keystone",
}

AGENT_ROLES = {
    "Lynx": "Product Operator",
    "Wildfire": "Growth & Distribution",
    "Bedrock": "Systems & Architecture",
    "Leverage": "Capital Allocator",
    "Sentinel": "Risk & Reality Check",
    "Prism": "Creative Director",
    "Razor": "Product Purist",
    "Keystone": "Board Orchestrator",
}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
