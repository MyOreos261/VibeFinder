"""
Thin wrapper around the Gemini API.

The rest of the system only calls generate_json(). It returns a dict, or None if
anything goes wrong (no key, network error, bad JSON). Callers treat None as
"fall back to the deterministic path", so the app never crashes because of the LLM.
"""

import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-lite-latest"


class GeminiClient:
    """Calls Gemini and asks for a JSON response."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        from google import genai  # imported here so offline mode works without the package

        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.client = genai.Client(api_key=key)
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

    def generate_json(self, prompt: str, temperature: float = 0.2) -> Optional[Dict]:
        """Send the prompt and parse the reply as JSON. Returns None on any failure."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={"response_mime_type": "application/json", "temperature": temperature},
            )
            text = (response.text or "").strip()
            data = json.loads(text)
            if not isinstance(data, dict):
                logger.warning("LLM returned JSON that is not an object: %.200s", text)
                return None
            return data
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned invalid JSON: %s", exc)
        except Exception as exc:  # network, auth, quota...
            logger.error("LLM call failed: %s: %s", type(exc).__name__, exc)
        return None


def make_client(offline: bool = False) -> Optional[GeminiClient]:
    """Return a GeminiClient, or None when offline or no key is configured."""
    if offline:
        logger.info("Offline mode: LLM disabled")
        return None
    try:
        return GeminiClient()
    except Exception as exc:
        logger.warning("LLM unavailable (%s); using the rule-based fallback", exc)
        return None
