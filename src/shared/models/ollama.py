from typing import Any, Dict, Optional, List
import httpx
import logging
import json
import asyncio
import time
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge


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
        
        # Initialize Prometheus metrics
        self.latency = Histogram(
            "ollama_request_duration_seconds",
            "Time spent processing Ollama requests",
            ["model_name", "status", "operation"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        self.tokens_processed = Counter(
            "ollama_tokens_total",
            "Total number of tokens processed",
            ["model_name", "type", "status"]
        )
        self.requests = Counter(
            "ollama_requests_total",
            "Total number of requests made to Ollama",
            ["model_name", "status", "operation"]
        )
        self.memory_usage = Gauge(
            "ollama_memory_bytes",
            "Estimated memory usage by model",
            ["model_name", "type"]
        )
        self.response_length = Histogram(
            "ollama_response_length_chars",
            "Length of model responses in characters",
            ["model_name", "status"],
            buckets=[50, 100, 250, 500, 1000, 2500, 5000]
        )
        self.queue_time = Histogram(
            "ollama_queue_time_seconds",
            "Time spent waiting in queue before processing",
            ["model_name"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )
        self.errors = Counter(
            "ollama_errors_total",
            "Total number of errors by type",
            ["model_name", "error_type"]
        )

    def _validate_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        if "response" not in response:
            raise ModelError("Invalid response format: missing 'response' field")
        
        try:
            result = json.loads(response["response"])
            input_tokens = len(response.get("prompt", "").split())
            output_tokens = len(response["response"].split())
            
            return {
                "text": response["response"],
                "parsed": result,
                "confidence": float(response.get("context", {}).get("confidence", 0.5)),
                "metadata": response.get("context", {}),
                "tokens": {
                    "input": input_tokens,
                    "output": output_tokens
                }
            }
        except json.JSONDecodeError:
            input_tokens = len(response.get("prompt", "").split())
            output_tokens = len(response["response"].split())
            return {
                "text": response["response"],
                "confidence": float(response.get("context", {}).get("confidence", 0.5)),
                "metadata": response.get("context", {}),
                "tokens": {
                    "input": input_tokens,
                    "output": output_tokens
                }
            }

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        last_error = None
        start_time = time.perf_counter()
        
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
                    
                    duration = time.perf_counter() - start_time
                    validated_response = self._validate_response(result)
                    
                    # Update metrics
                    queue_time = time.perf_counter() - start_time - duration
                    self.queue_time.labels(model_name=self.model_name).observe(queue_time)
                    
                    self.latency.labels(
                        model_name=self.model_name,
                        status="success",
                        operation="generate"
                    ).observe(duration)
                    self.requests.labels(
                        model_name=self.model_name,
                        status="success",
                        operation="generate"
                    ).inc()
                    self.tokens_processed.labels(
                        model_name=self.model_name,
                        type="input",
                        status="success"
                    ).inc(validated_response["tokens"]["input"])
                    self.tokens_processed.labels(
                        model_name=self.model_name,
                        type="output",
                        status="success"
                    ).inc(validated_response["tokens"]["output"])
                    self.response_length.labels(
                        model_name=self.model_name,
                        status="success"
                    ).observe(len(validated_response["text"]))
                    
                    # Estimate memory usage (rough estimate: 4 bytes per token)
                    total_tokens = validated_response["tokens"]["input"] + validated_response["tokens"]["output"]
                    self.memory_usage.labels(
                        model_name=self.model_name,
                        type="total"
                    ).set(total_tokens * 4)
                    
                    return validated_response

            except httpx.ReadTimeout as e:
                last_error = e
                self.logger.warning(f"Timeout during Ollama API call (attempt {attempt + 1}/{self.max_retries})")
                self.requests.labels(
                    model_name=self.model_name,
                    status="timeout",
                    operation="generate"
                ).inc()
                self.errors.labels(
                    model_name=self.model_name,
                    error_type="timeout"
                ).inc()
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

            except (httpx.HTTPError, json.JSONDecodeError) as e:
                error_type = type(e).__name__
                error_msg = str(e)
                self.logger.error(f"{error_type} during Ollama API call: {error_msg}")
                self.requests.labels(
                    model_name=self.model_name,
                    status="error",
                    operation="generate"
                ).inc()
                self.errors.labels(
                    model_name=self.model_name,
                    error_type=error_type.lower()
                ).inc()
                self.latency.labels(
                    model_name=self.model_name,
                    status="error",
                    operation="generate"
                ).observe(time.perf_counter() - start_time)
                raise ModelError(f"{error_type}: {error_msg}")
            
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                self.logger.error(f"Unexpected {error_type} during Ollama API call: {error_msg}")
                self.requests.labels(
                    model_name=self.model_name,
                    status="error",
                    operation="generate"
                ).inc()
                self.errors.labels(
                    model_name=self.model_name,
                    error_type="unexpected"
                ).inc()
                self.latency.labels(
                    model_name=self.model_name,
                    status="error",
                    operation="generate"
                ).observe(time.perf_counter() - start_time)
                raise ModelError(f"Unexpected error: {error_msg}")

        self.requests.labels(
            model_name=self.model_name,
            status="timeout",
            operation="generate"
        ).inc()
        self.errors.labels(
            model_name=self.model_name,
            error_type="max_retries_exceeded"
        ).inc()
        self.latency.labels(
            model_name=self.model_name,
            status="timeout",
            operation="generate"
        ).observe(time.perf_counter() - start_time)
        raise ModelError(f"Model response timeout after {self.max_retries} retries: {str(last_error)}")

    async def generate_batch(self, prompts: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = await asyncio.gather(
            *[self.generate(prompt, **kwargs) for prompt in prompts],
            return_exceptions=True
        )
        processed_results: List[Dict[str, Any]] = []
        
        for result in results:
            if isinstance(result, Exception):
                self.requests.labels(model_name=self.model_name, status="error").inc()
                processed_results.append({
                    "error": str(result),
                    "success": False,
                    "text": "",
                    "confidence": 0.0,
                    "metadata": {},
                    "parsed": {},
                    "tokens": {"input": 0, "output": 0}
                })
            else:
                # Ensure result is properly typed
                if isinstance(result, dict):
                    processed_results.append(result)
                else:
                    processed_results.append({
                        "error": "Invalid response format",
                        "success": False,
                        "text": str(result),
                        "confidence": 0.0,
                        "metadata": {},
                        "parsed": {},
                        "tokens": {"input": 0, "output": 0}
                    })
        
        # Record batch metrics
        total_tokens = sum(
            result.get("tokens", {}).get("input", 0) + result.get("tokens", {}).get("output", 0)
            for result in processed_results
        )
        self.memory_usage.labels(model_name=self.model_name).set(total_tokens * 4)
        
        return processed_results
