from typing import Any, Dict, Optional, List
import httpx
import logging
import json
import asyncio
from datetime import datetime


class ModelError(Exception):
    pass


class OllamaModel:
    def __init__(self, model_name: str = "deepseek-r1:8b"):
        self.model_name = model_name
        self.base_url = "http://localhost:11434/api"
        self.logger = logging.getLogger(__name__)
        self.timeout = 30.0
        self.max_retries = 3
        self.retry_delay = 1.0

    def _validate_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        if "response" not in response:
            raise ModelError("Invalid response format: missing 'response' field")
        
        try:
            result = json.loads(response["response"])
            return {
                "text": response["response"],
                "parsed": result,
                "confidence": float(response.get("context", {}).get("confidence", 0.5)),
                "metadata": response.get("context", {})
            }
        except json.JSONDecodeError:
            return {
                "text": response["response"],
                "confidence": float(response.get("context", {}).get("confidence", 0.5)),
                "metadata": response.get("context", {})
            }

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/generate",
                        json={
                            "model": self.model_name,
                            "prompt": prompt,
                            "stream": False,
                            **kwargs
                        },
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                    result = await response.json()
                    if not isinstance(result, dict):
                        raise ModelError("Invalid response format: response must be a dictionary")
                    return self._validate_response(result)

            except httpx.ReadTimeout as e:
                last_error = e
                self.logger.warning(f"Timeout during Ollama API call (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

            except (httpx.HTTPError, json.JSONDecodeError, Exception) as e:
                error_type = type(e).__name__
                error_msg = str(e)
                self.logger.error(f"{error_type} during Ollama API call: {error_msg}")
                raise ModelError(f"{error_type}: {error_msg}")

        raise ModelError(f"Model response timeout after {self.max_retries} retries: {str(last_error)}")

    async def generate_batch(self, prompts: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = await asyncio.gather(
            *[self.generate(prompt, **kwargs) for prompt in prompts],
            return_exceptions=True
        )
        processed_results: List[Dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    "error": str(result),
                    "success": False,
                    "text": "",
                    "confidence": 0.0,
                    "metadata": {},
                    "parsed": {}
                })
            else:
                processed_results.append(result)
        return processed_results
