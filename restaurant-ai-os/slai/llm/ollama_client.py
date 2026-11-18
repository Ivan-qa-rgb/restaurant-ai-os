import os

import requests

from slai.config import OLLAMA_BASE_URL, OLLAMA_MODEL

class OllamaClient:
    def __init__(self, base_url=None, model=None, timeout=None):
        self.base_url = base_url or OLLAMA_BASE_URL
        self.model = model or OLLAMA_MODEL
        self.timeout = timeout or int(os.getenv("OLLAMA_TIMEOUT", "300"))

    def generate(self, prompt, system=None, format=None):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "num_predict": 200,
            },
        }

        if system:
            payload["system"] = system

        if format:
            payload["format"] = format

        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("response", "")
