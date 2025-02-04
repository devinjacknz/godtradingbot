from typing import Any, Dict
import httpx


class OllamaModel:
    def __init__(self, model_name: str = "deepseek-r1:1.5b"):
        self.model_name = model_name
        self.base_url = "http://localhost:11434/api"

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/generate",
                json={"model": self.model_name, "prompt": prompt, "stream": False},
            )
            result = response.json()
            return {
                "text": result["response"],
                "confidence": float(result.get("context", {}).get("confidence", 0.5)),
            }
