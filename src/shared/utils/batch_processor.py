import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from src.shared.monitor.metrics import track_batch_utilization


class BatchProcessingError(Exception):
    """Raised when batch processing fails"""

    def __init__(self, message: str, batch_id: Optional[int] = None):
        self.batch_id = batch_id
        super().__init__(message)


T = TypeVar("T")
R = TypeVar("R")


class BatchProcessor(Generic[T, R]):
    def __init__(self, max_batch: int = 16, timeout: int = 50):
        self.batch: List[T] = []
        self.max_batch = max_batch
        self.timeout = timeout
        self.processing = False
        self._lock = asyncio.Lock()
        self.results: Dict[int, List[R]] = {}
        self._errors: Dict[int, Exception] = {}
        self._current_batch_id = 0
        self._shutdown = False

    async def shutdown(self):
        try:
            self._shutdown = True
            async with self._lock:
                if self.batch:
                    try:
                        await self._flush()
                    except Exception:
                        pass
                self.processing = False
                self.batch.clear()
                self.results.clear()
                self._errors.clear()
        except Exception:
            self.processing = False
            self.batch.clear()
            self.results.clear()
            self._errors.clear()

    async def _process_items(self, items: List[T]) -> List[R]:
        """Process a batch of items. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _process_items")

    async def process(self, request: Union[T, List[T]]) -> Union[Optional[R], List[R]]:
        from src.shared.monitor.metrics import track_batch_size, track_batch_utilization

        # Handle list requests directly
        if isinstance(request, list):
            if not request:
                raise ValueError("Empty batch")
            batch_len = len(request)
            track_batch_size(batch_len)
            track_batch_utilization(batch_len / self.max_batch)
            try:
                async with self._lock:
                    results = await asyncio.wait_for(
                        self._process_batch(request), timeout=self.timeout / 1000
                    )
                    if results is None:
                        raise BatchProcessingError("Invalid batch result")
                    if len(results) != len(request):
                        raise BatchProcessingError("Batch result count mismatch")
                    return results
            except asyncio.TimeoutError:
                raise BatchProcessingError("Request timed out")
            except BatchProcessingError as e:
                raise e
            except Exception as e:
                logging.error(f"Error processing batch: {str(e)}")
                raise BatchProcessingError(str(e))

        # Handle single item
        try:
            async with self._lock:
                # Clean up old results before processing
                if len(self.results) > 100:
                    oldest_batch_ids = sorted(self.results.keys())[:-50]
                    for old_id in oldest_batch_ids:
                        del self.results[old_id]
                        if old_id in self._errors:
                            del self._errors[old_id]

                # Add request to batch
                self.batch.append(request)
                batch_id = self._current_batch_id

                # Process immediately if batch is full
                if len(self.batch) >= self.max_batch:
                    try:
                        results = await asyncio.wait_for(
                            self._process_batch(self.batch.copy()),
                            timeout=self.timeout / 1000,
                        )
                        self.results[batch_id] = results
                        self.batch.clear()
                        self._current_batch_id += 1
                        return results[-1]
                    except asyncio.TimeoutError:
                        if request in self.batch:
                            self.batch.remove(request)
                        raise BatchProcessingError("Request timed out")
                    except BatchProcessingError as e:
                        if request in self.batch:
                            self.batch.remove(request)
                        raise e
                    except Exception as e:
                        if request in self.batch:
                            self.batch.remove(request)
                        error_msg = f"Error processing batch: {str(e)}"
                        logging.error(error_msg)
                        raise BatchProcessingError(error_msg)

                # Start delayed flush if not already processing
                if not self.processing:
                    self.processing = True
                    asyncio.create_task(self._delayed_flush())

            # Wait for result outside lock
            try:
                result = await asyncio.wait_for(
                    self._wait_for_result(request), timeout=self.timeout / 1000
                )
                if result is not None:
                    return result
                raise BatchProcessingError("Result not found")
            except asyncio.TimeoutError:
                async with self._lock:
                    if request in self.batch:
                        self.batch.remove(request)
                raise BatchProcessingError("Request timed out")
            except BatchProcessingError as e:
                async with self._lock:
                    if request in self.batch:
                        self.batch.remove(request)
                raise e
            except Exception as e:
                async with self._lock:
                    if request in self.batch:
                        self.batch.remove(request)
                error_msg = f"Error processing request: {str(e)}"
                logging.error(error_msg)
                raise BatchProcessingError(error_msg)
        except Exception as e:
            logging.error(f"Unexpected error in process: {str(e)}")
            raise BatchProcessingError(str(e))

    async def _delayed_flush(self):
        try:
            await asyncio.sleep(self.timeout / 1000)
            async with self._lock:
                if self.batch:
                    batch_id = self._current_batch_id
                    try:
                        # Clean up old results before processing
                        if len(self.results) > 100:
                            oldest_batch_ids = sorted(self.results.keys())[:-50]
                            for old_id in oldest_batch_ids:
                                del self.results[old_id]
                                if old_id in self._errors:
                                    del self._errors[old_id]

                        results = await asyncio.wait_for(
                            self._process_batch(self.batch.copy()),
                            timeout=self.timeout / 1000,
                        )
                        self.results[batch_id] = results
                        self.batch.clear()
                        self._current_batch_id += 1
                    except asyncio.TimeoutError:
                        self.batch.clear()
                        error = BatchProcessingError("Request timed out", batch_id)
                        self._errors[batch_id] = error
                        raise error
                    except BatchProcessingError as e:
                        self.batch.clear()
                        if e.batch_id in self.results:
                            del self.results[e.batch_id]
                        self._errors[batch_id] = e
                        raise e
                    except Exception as e:
                        self.batch.clear()
                        error = BatchProcessingError(str(e), batch_id)
                        self._errors[batch_id] = error
                        raise error
        finally:
            self.processing = False

    async def _process_batch(self, batch: List[T]) -> List[R]:
        if not batch:
            raise ValueError("Empty batch")

        batch_id = self._current_batch_id
        try:
            async with self._lock:
                # Clean up old results before processing
                if len(self.results) > 100:
                    oldest_batch_ids = sorted(self.results.keys())[:-50]
                    for old_id in oldest_batch_ids:
                        del self.results[old_id]
                        if old_id in self._errors:
                            del self._errors[old_id]

                results = await asyncio.wait_for(
                    self._process_items(batch), timeout=self.timeout / 1000
                )

                if results is None:
                    error = BatchProcessingError("Invalid batch result", batch_id)
                    self._errors[batch_id] = error
                    raise error

                if len(results) != len(batch):
                    error = BatchProcessingError("Invalid batch result size", batch_id)
                    self._errors[batch_id] = error
                    raise error

                self.results[batch_id] = results
                self._current_batch_id += 1
                return results

        except asyncio.TimeoutError:
            error = BatchProcessingError("Request timed out", batch_id)
            self._errors[batch_id] = error
            raise error
        except BatchProcessingError as e:
            self._errors[batch_id] = e
            raise e
        except Exception as e:
            error = BatchProcessingError(str(e), batch_id)
            self._errors[batch_id] = error
            raise error

    async def _process_items(self, items: List[T]) -> List[R]:
        """Process a batch of items. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _process_items")

    async def _flush(self) -> List[R]:
        if not self.batch:
            raise ValueError("Empty batch")

        batch = self.batch.copy()
        self.batch.clear()
        batch_id = self._current_batch_id
        self._current_batch_id += 1

        # Clean up old results before processing new batch
        async with self._lock:
            if len(self.results) > 100:
                oldest_batch_ids = sorted(self.results.keys())[:-50]
                for old_id in oldest_batch_ids:
                    del self.results[old_id]
                    if old_id in self._errors:
                        del self._errors[old_id]

        from src.shared.monitor.metrics import track_batch_size, track_batch_utilization

        batch_len = len(batch)
        track_batch_size(batch_len)
        track_batch_utilization(batch_len / float(self.max_batch))

        try:
            results = await asyncio.wait_for(
                self._process_batch(batch), timeout=self.timeout / 1000
            )
            async with self._lock:
                self.results[batch_id] = results
                # Clean up old results after adding new ones
                if len(self.results) > 100:
                    oldest_batch_ids = sorted(self.results.keys())[:-50]
                    for old_id in oldest_batch_ids:
                        del self.results[old_id]
                        if old_id in self._errors:
                            del self._errors[old_id]
            return results
        except asyncio.TimeoutError:
            error = BatchProcessingError("Request timed out", batch_id)
            self._errors[batch_id] = error
            raise error
        except BatchProcessingError as e:
            if batch_id in self.results:
                del self.results[batch_id]
            self._errors[batch_id] = e
            raise e
        except Exception as e:
            if batch_id in self.results:
                del self.results[batch_id]
            error = BatchProcessingError(f"Error processing batch: {str(e)}", batch_id)
            self._errors[batch_id] = error
            raise error

    async def _wait_for_result(self, request: T) -> Optional[R]:
        start_time = time.time()
        while True:
            async with self._lock:
                # Clean up old results first
                if len(self.results) > 100:
                    oldest_batch_ids = sorted(self.results.keys())[:-50]
                    for old_id in oldest_batch_ids:
                        del self.results[old_id]
                        if old_id in self._errors:
                            del self._errors[old_id]

                # Check if request is still in batch
                if request not in self.batch:
                    # Look for result in most recent batches first
                    for batch_id, results in sorted(self.results.items(), reverse=True):
                        if not results:
                            continue
                        for result in results:
                            if isinstance(request, dict) and isinstance(result, dict):
                                if all(request[k] == result.get(k) for k in request):
                                    return result
                            elif request == result:
                                return result
                            elif hasattr(request, "__dict__") and hasattr(
                                result, "__dict__"
                            ):
                                if request.__dict__ == result.__dict__:
                                    return result

                # Check for errors
                for batch_id, error in sorted(self._errors.items(), reverse=True):
                    if isinstance(error, BatchProcessingError):
                        if request in self.batch:
                            self.batch.remove(request)
                        raise error

            # Check for timeout
            if time.time() - start_time > self.timeout / 1000:
                async with self._lock:
                    if request in self.batch:
                        self.batch.remove(request)
                    error = BatchProcessingError("Request timed out", None)
                    self._errors[self._current_batch_id] = error
                    raise error

            await asyncio.sleep(0.01)
