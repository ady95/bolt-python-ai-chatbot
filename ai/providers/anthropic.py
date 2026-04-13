from .base_provider import BaseAPIProvider
import anthropic
import os
import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class AnthropicAPI(BaseAPIProvider):
    MODELS = {
        "claude-opus-4-6": {
            "name": "Claude Opus 4.6",
            "provider": "Anthropic",
            "max_tokens": 8192,
        },
        "claude-sonnet-4-6": {
            "name": "Claude Sonnet 4.6",
            "provider": "Anthropic",
            "max_tokens": 8192,
        },
        "claude-haiku-4-5-20251001": {
            "name": "Claude Haiku 4.5",
            "provider": "Anthropic",
            "max_tokens": 8192,
        },
    }

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")

    def set_model(self, model_name: str):
        if model_name not in self.MODELS.keys():
            raise ValueError("Invalid model")
        self.current_model = model_name

    def get_models(self) -> dict:
        if self.api_key is not None:
            return self.MODELS
        else:
            return {}

    def generate_response(self, prompt: str, system_content: str) -> str:
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            response = self.client.messages.create(
                model=self.current_model,
                system=system_content,
                messages=[
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                max_tokens=self.MODELS[self.current_model]["max_tokens"],
            )
            return response.content[0].text
        except anthropic.APIConnectionError as e:
            logger.error(f"Server could not be reached: {e.__cause__}")
            raise e
        except anthropic.RateLimitError as e:
            logger.error(f"A 429 status code was received. {e}")
            raise e
        except anthropic.AuthenticationError as e:
            logger.error(f"There's an issue with your API key. {e}")
            raise e
        except anthropic.APIStatusError as e:
            logger.error(
                f"Another non-200-range status code was received: {e.status_code}"
            )
            raise e
