import json
import os
from state_store.user_identity import UserIdentity
import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "Anthropic")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "claude-sonnet-4-6")


def get_user_state(user_id: str, is_app_home: bool):
    filepath = f"./data/{user_id}"
    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as file:
                user_identity: UserIdentity = json.load(file)
                return user_identity["provider"], user_identity["model"]
        if is_app_home:
            return None
        logger.info(
            f"No provider selection found for user {user_id}. "
            f"Falling back to default: {DEFAULT_PROVIDER}/{DEFAULT_MODEL}"
        )
        return DEFAULT_PROVIDER, DEFAULT_MODEL
    except Exception as e:
        logger.error(e)
        raise e
