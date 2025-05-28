import asyncio
import functools
import logging
import time


def retry_execution(attempts, delay=0, sync_to_thread=False):
    def decorator(func):
        @functools.wraps(func)
        async def awrapped_func(*args, **kwargs):
            last_exception = None
            for attempt in range(attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    return await asyncio.to_thread(func, *args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logging.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}"
                    )
                    if delay > 0 and attempt < attempts - 1:
                        await asyncio.sleep(delay)
            # If the loop finishes and the function didn't return successfully
            logging.error(f"All {attempts} attempts failed for {func.__name__}")
            raise last_exception

        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            last_exception = None
            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logging.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}"
                    )
                    if delay > 0 and attempt < attempts - 1:
                        time.sleep(delay)
            # If the loop finishes and the function didn't return successfully
            logging.error(f"All {attempts} attempts failed for {func.__name__}")
            raise last_exception

        if sync_to_thread or asyncio.iscoroutinefunction(func):
            return awrapped_func
        return wrapped_func

    return decorator
