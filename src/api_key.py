"""API key validation middleware.

Checks incoming requests against the configured API keys in config.json.
Supports both a single shared key (api_key) and named per-device keys (api_keys).
"""

import logging
from typing import Optional, Tuple

from src.config_manager import ConfigManager

logger = logging.getLogger(__name__)


def validate_api_key(
    config: ConfigManager,
    header_value: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """Validate an API key from an incoming request.

    Args:
        config: ConfigManager instance (reads api_key, api_keys, api_key_enabled).
        header_value: The value of the X-API-Key (or Authorization: Bearer) header.

    Returns:
        (True, key_name) if valid — key_name is 'shared' for the shared key,
            or the device name for a named key.
        (False, None) if invalid or missing.
    """
    # Master toggle
    enabled: bool = config.get("api_key_enabled", False)
    if not enabled:
        return True, None

    if not header_value:
        logger.warning("API key required but not provided")
        return False, None

    key = header_value.strip()
    if not key:
        logger.warning("API key header present but empty")
        return False, None

    # Check shared key
    shared_key: str = config.get("api_key", "")
    if shared_key and key == shared_key:
        logger.info("Authenticated request from 'shared'")
        return True, "shared"

    # Check named keys
    named_keys: dict = config.get("api_keys", {})
    for name, stored_key in named_keys.items():
        if key == stored_key:
            logger.info("Authenticated request from '%s'", name)
            return True, name

    logger.warning("API key did not match any configured key")
    return False, None
