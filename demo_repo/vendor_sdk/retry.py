import random
import time


def retry_with_backoff(request_fn, max_retries=5, base_delay=1.0):
    """Retry a request with exponential backoff and jitter.

    Retries only on 429/5xx. Delay doubles each attempt, capped at 60s.
    Raises the last error after max_retries attempts.
    """
    for attempt in range(max_retries):
        try:
            resp = request_fn()
            if resp.status_code < 400:
                return resp
            if resp.status_code not in (429, 500, 502, 503, 504):
                resp.raise_for_status()
        except ConnectionError:
            pass
        delay = min(base_delay * (2 ** attempt), 60.0)
        time.sleep(delay + random.uniform(0, 0.5))
    raise RuntimeError(f"request failed after {max_retries} retries")
