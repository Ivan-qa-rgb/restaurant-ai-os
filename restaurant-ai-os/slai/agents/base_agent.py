from slai.llm.ollama_client import OllamaClient

class BaseAgent:
    name = "base_agent"
    system_prompt = ""

    def __init__(self, client=None):
        self.client = client or OllamaClient()

    def run(self, prompt, format=None):
        return self.client.generate(
            prompt,
            system=self.system_prompt,
            format=format,
        )
