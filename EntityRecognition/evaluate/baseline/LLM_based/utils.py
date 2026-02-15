import requests
import os
from functools import wraps
from tenacity import retry, stop_after_attempt, wait_exponential

API_URL = "https://tianshu.tones-ai.com/v1/chat/completions"

# Config file path
CONFIG_FILE = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/env.conf"


def load_api_key_from_conf(conf_path):
    if not os.path.exists(conf_path):
        # If file not found, try reading from environment variable, or return empty
        return os.getenv("CHAINNODE_API_KEY", "")

    api_key = ""
    try:
        with open(conf_path, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments or empty lines
                if not line or line.startswith("#"):
                    continue

                # Look for llm_API
                if line.startswith("llm_API"):
                    # Split by first '='
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        # Remove surrounding spaces, double quotes, single quotes
                        api_key = parts[1].strip().strip('"').strip("'")
                        break
    except Exception as e:
        print(f"[Warning] Failed to read {conf_path}: {e}")

    return api_key


# --- Initialize API_KEY ---
API_KEY = load_api_key_from_conf(CONFIG_FILE)

# Simple check
if not API_KEY:
    print(f"[Warning] 'llm_API' not found in {CONFIG_FILE}, and env var not set. API calls may fail.")


@retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, max=10))
def chainnode_chat_complete(messages, model, **kwargs):
    """
    Call Chainnode API using requests library
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": model,
        "messages": messages,
        **kwargs
    }

    # Send POST request
    response = requests.post(API_URL, headers=headers, json=payload)

    # Check for HTTP errors
    response.raise_for_status()

    # Return JSON dictionary
    return response.json()


class APICostCalculator:
    """
    Calculate API Cost (Adapted for JSON dict response format)
    """
    # Estimated price (USD per 1M tokens)
    _model_cost_per_1m_tokens = {
        "gpt-5-mini": {"prompt": 0.15, "completion": 0.60},
        "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    }

    def __init__(self, model_name: str = "gpt-5-mini"):
        self._model_name = model_name
        self._cost = 0

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get response (dict format)
            response = func(*args, **kwargs)

            # Parse Usage
            usage = response.get("usage", {})
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                costs = self._model_cost_per_1m_tokens.get(self._model_name, {"prompt": 0, "completion": 0})

                self._cost += (prompt_tokens / 1_000_000) * costs["prompt"]
                self._cost += (completion_tokens / 1_000_000) * costs["completion"]

            return response

        return wrapper

    @property
    def cost(self):
        return self._cost