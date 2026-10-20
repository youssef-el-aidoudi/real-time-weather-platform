"""
Open-Meteo HTTP client with retry logic and structured logging.
"""
import logging
import time

import requests

logger = logging.getLogger(__name__)


def fetch_data(url: str, max_retries: int = 3, backoff: float = 2.0) -> dict:
    """
    Fetch JSON data from a URL with exponential-backoff retries.

    Args:
        url:         Full URL with query parameters.
        max_retries: Maximum number of attempts before raising.
        backoff:     Base delay multiplier (seconds). Delay = backoff^attempt.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        requests.RequestException: After all retries are exhausted.
    """
    last_error: Exception = RuntimeError("No attempts made")

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Open-Meteo request (attempt %d/%d): %s", attempt, max_retries, url)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            logger.info("Open-Meteo response OK (HTTP %d)", response.status_code)
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                delay = backoff ** attempt
                logger.info("Retrying in %.1fs ...", delay)
                time.sleep(delay)

    logger.error("All %d attempts failed for %s", max_retries, url)
    raise last_error
