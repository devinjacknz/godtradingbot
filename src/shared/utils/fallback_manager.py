import asyncio
import logging
from typing import Any, Generic, List, Optional, TypeVar

from tradingbot.shared.monitor.metrics import track_fallback_rate, track_model_fallback

T = TypeVar("T")
R = TypeVar("R")


class FallbackManager(Generic[T, R]):
    def __init__(
        self,
        new_system: Any,
        legacy_system: Any,
        timeout: Optional[float] = None,
        handled_exceptions: Optional[tuple[Exception, ...]] = None,
        max_retries: int = 0,
    ):
        self.new = new_system
        self.old = legacy_system
        self.timeout = timeout
        self.handled_exceptions = handled_exceptions or (Exception,)
        self.max_retries = max_retries
        self._lock = asyncio.Lock()

    async def _try_process(self, system: Any, request: T) -> Optional[R]:
        if hasattr(system, "process"):
            return await system.process(request)
        elif hasattr(system, "generate"):
            return await system.generate(request)
        raise AttributeError("System has no process/generate method")

    async def execute(self, request: T) -> Optional[R]:
        async with self._lock:
            for retry in range(self.max_retries + 1):
                try:
                    if self.timeout:
                        result = await asyncio.wait_for(
                            self._try_process(self.new, request), self.timeout
                        )
                    else:
                        result = await self._try_process(self.new, request)

                    if result is None:
                        if retry == self.max_retries:
                            track_fallback_rate(success=False)
                            break
                        continue

                    track_fallback_rate(success=True)
                    return result

                except asyncio.TimeoutError:
                    logging.warning(
                        "Primary system timed out (attempt %d/%d)",
                        retry + 1,
                        self.max_retries + 1
                    )
                    if retry == self.max_retries:
                        track_fallback_rate(success=False)
                        break
                    continue
                except Exception as e:
                    if (
                        not isinstance(e, self.handled_exceptions)
                        or retry == self.max_retries
                    ):
                        track_fallback_rate(success=False)
                        break
                    logging.warning(
                        "Primary system failed (attempt %d/%d): %s",
                        retry + 1,
                        self.max_retries + 1,
                        str(e)
                    )
                    continue

            logging.warning("Switching to legacy system")
            track_model_fallback()

            try:
                if self.timeout:
                    result = await asyncio.wait_for(
                        self._try_process(self.old, request), self.timeout
                    )
                else:
                    result = await self._try_process(self.old, request)

                if result is None:
                    track_fallback_rate(success=False)
                    raise ValueError("Invalid result from legacy system")
                track_fallback_rate(success=True)
                return result

            except Exception as e:
                track_fallback_rate(success=False)
                logging.error("Both systems failed: %s", str(e))
                raise RuntimeError("Both systems failed: %s" % str(e)) from e

    async def execute_batch(self, requests: List[T]) -> List[Optional[R]]:
        async with self._lock:
            try:
                if hasattr(self.new, "generate_batch"):
                    try:
                        results: List[R] = await self.new.generate_batch(requests)
                        if results and len(results) == len(requests):
                            track_fallback_rate(success=True)
                            return results
                    except Exception as e:
                        logging.warning("Batch generation failed: %s", str(e))
                        track_fallback_rate(success=False)

                if hasattr(self.new, "process"):
                    try:
                        result = await self.new.process(requests)
                        if isinstance(result, list) and len(result) == len(requests):
                            track_fallback_rate(success=True)
                            return result
                        elif result is not None:
                            track_fallback_rate(success=True)
                            return [result] * len(requests)
                    except Exception as e:
                        logging.warning("Batch processing failed: %s", str(e))
                        track_fallback_rate(success=False)

                results = []
                success_count = 0
                for request in requests:
                    try:
                        result = await self.execute(request)
                        if result is not None:
                            success_count += 1
                        results.append(result)
                    except Exception as e:
                        logging.warning("Individual request failed: %s", str(e))
                        results.append(None)

                if success_count > 0:
                    track_fallback_rate(success=True)
                    return results

                logging.warning("Switching to legacy system for batch")
                track_model_fallback()

                if hasattr(self.old, "process"):
                    try:
                        results = await self.old.process(requests)
                        if results and len(results) == len(requests):
                            track_fallback_rate(success=True)
                            return results
                    except Exception as e:
                        logging.warning("Legacy batch processing failed: %s", str(e))
                        track_fallback_rate(success=False)

                results = []
                success_count = 0
                for request in requests:
                    try:
                        result = await self.old.generate(request)
                        if result is not None:
                            success_count += 1
                        results.append(result)
                    except Exception as e:
                        logging.warning("Legacy individual request failed: %s", str(e))
                        results.append(None)

                track_fallback_rate(success=success_count > 0)
                return results

            except Exception as e:
                logging.error("Complete batch processing failure: %s", str(e))
                track_fallback_rate(success=False)
                return [None] * len(requests)
