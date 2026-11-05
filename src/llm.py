"""
Thin wrapper around the Gemini API.

The rest of the system only calls generate_json(). It returns a dict, or None if
anything goes wrong (no key, network error, bad JSON). Callers treat None as
"fall back to the deterministic path", so the app never crashes because of the LLM.
"""

import json
import logging
import os
import re
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-lite-latest"
RETRY_HINT = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)


class GeminiClient:
    """Calls Gemini and asks for a JSON response."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 min_interval: float = 0.0, max_retries: int = 4):
        from google import genai  # imported here so offline mode works without the package

        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.client = genai.Client(api_key=key)
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        # Seconds to keep between calls (the free tier allows 15 requests/minute -> 4.1s).
        self.min_interval = float(os.getenv("GEMINI_MIN_INTERVAL", min_interval))
        self.max_retries = max_retries
        self.calls = 0          # successful API responses
        self.failures = 0       # calls that still failed after all retries
        self._last_call = 0.0

    def _wait_for_slot(self) -> None:
        wait = self._last_call + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _request(self, prompt: str, temperature: float) -> str:
        """Call the API, retrying rate-limit (429) and overload (503) errors with backoff."""
        for attempt in range(self.max_retries + 1):
            self._wait_for_slot()
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": temperature},
                )
                return (response.text or "").strip()
            except Exception as exc:
                message = str(exc)
                retryable = any(code in message for code in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"))
                if not retryable or attempt == self.max_retries:
                    raise
                hint = RETRY_HINT.search(message)
                delay = min(60.0, float(hint.group(1)) + 1 if hint else 2 ** (attempt + 1))
                logger.warning("LLM busy (%s), retry %d/%d in %.0fs",
                               message[:40], attempt + 1, self.max_retries, delay)
                time.sleep(delay)
        raise RuntimeError("unreachable")

    def generate_json(self, prompt: str, temperature: float = 0.2) -> Optional[Dict]:
        """Send the prompt and parse the reply as JSON. Returns None on any failure."""
        try:
            text = self._request(prompt, temperature)
            self.calls += 1
            data = json.loads(text)
            if not isinstance(data, dict):
                logger.warning("LLM returned JSON that is not an object: %.200s", text)
                return None
            return data
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned invalid JSON: %s", exc)
            return None
        except Exception as exc:  # network, auth, quota after retries...
            self.failures += 1
            logger.error("LLM call failed: %s: %.300s", type(exc).__name__, exc)
        return None


def make_client(offline: bool = False, min_interval: float = 0.0) -> Optional[GeminiClient]:
    """Return a GeminiClient, or None when offline or no key is configured."""
    if offline:
        logger.info("Offline mode: LLM disabled")
        return None
    try:
        return GeminiClient(min_interval=min_interval)
    except Exception as exc:
        logger.warning("LLM unavailable (%s); using the rule-based fallback", exc)
        return None
