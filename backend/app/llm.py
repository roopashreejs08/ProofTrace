import json
import re
import time

from .config import settings


def _extract_json(text):
    """Parse a JSON object out of a model reply, tolerating code fences."""

    if not text:
        return None

    text = re.sub(
        r"^```(?:json)?|```$",
        "",
        text.strip(),
        flags=re.M,
    ).strip()

    try:
        return json.loads(text)
    except ValueError:
        pass

    # Fall back to the first {...} block.
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            return None

    return None


# Names that are not general text models.
_SKIP = (
    "tts", "image", "audio", "embedding", "embed", "aqa", "live",
    "robotics", "veo", "lyria", "imagen", "gemma", "thinking",
    "native-audio", "vision",
)


# The GenAI SDK defaults to the stable "v1" endpoint, but the "-latest"
# and preview Gemini models are only served from "v1beta". Calling v1
# returns 404 ("not found for API version v1"), which previously made
# every AI call fail and the whole pipeline fall back to keyword
# matching. Pinning the version here is the fix.
GEMINI_API_VERSION = "v1beta"


def _http_options(types):
    """Build HttpOptions that pin the API version and a call timeout."""

    timeout_ms = int(settings.llm_timeout * 1000)

    try:
        return types.HttpOptions(
            api_version=GEMINI_API_VERSION,
            timeout=timeout_ms,
        )
    except Exception:
        return {
            "api_version": GEMINI_API_VERSION,
            "timeout": timeout_ms,
        }


class LLM:
    """Thin Gemini wrapper.

    Returns None on any failure so agents can fall back, but it records
    why it failed (``last_error``) and whether it ever succeeded
    (``used`` / ``failed`` counters) so the UI can tell genuine AI
    analysis apart from the keyword fallback.

    The configured model may disappear over time. When that happens the
    wrapper resolves a working model from the live model list instead of
    silently returning nothing.
    """

    def __init__(self):
        self.enabled = bool(settings.gemini_api_key)
        self.model = settings.gemini_model
        self.last_error = ""
        self.used = 0
        self.failed = 0
        self._client = None
        self._resolve_attempted = False

        if self.enabled:
            try:
                from google import genai
                from google.genai import types

                self._types = types

                self._client = genai.Client(
                    api_key=settings.gemini_api_key,
                    http_options=_http_options(types),
                )

            except Exception as e:
                self.enabled = False
                self.last_error = "Gemini client unavailable: " + str(e)

    # -- public ---------------------------------------------------------

    def json(self, prompt):
        if not self.enabled or self._client is None:
            return None

        for model in self._candidates():
            data = self._try_model(model, prompt)

            if data is not None:
                self.model = model
                self.used += 1
                self.last_error = ""
                return data

        self.failed += 1
        return None

    @property
    def working(self):
        return self.enabled and self.used > 0

    # -- internals ------------------------------------------------------

    def _candidates(self):
        out = [settings.gemini_model] + settings.gemini_fallbacks

        if self._resolve_attempted:
            return _unique(out)

        self._resolve_attempted = True

        for m in self._discover():
            out.append(m)

        return _unique(out)

    def _discover(self):
        """List models that support generateContent, flash models first."""

        try:
            models = []

            for m in self._client.models.list():
                name = getattr(m, "name", "") or ""
                methods = (
                    getattr(m, "supported_actions", None)
                    or getattr(m, "supported_generation_methods", None)
                    or []
                )

                if methods and "generateContent" not in methods:
                    continue

                short = name.split("/")[-1]

                if not short.startswith("gemini"):
                    continue

                if any(s in short for s in _SKIP):
                    continue

                models.append(short)

            def rank(n):
                return (
                    0 if "flash" in n else 1,
                    1 if "preview" in n else 0,
                    0 if "latest" in n else 1,
                    n,
                )

            return sorted(set(models), key=rank)

        except Exception as e:
            self.last_error = "Model list failed: " + str(e)
            return []

    def _try_model(self, model, prompt):
        try:
            resp = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                },
            )

            data = _extract_json(resp.text or "")

            if data is None:
                self.last_error = (
                    model + " returned no parseable JSON."
                )

            return data

        except Exception as e:
            msg = str(e)

            self.last_error = model + ": " + msg[:300]

            # Give overloaded / transient models one quick retry.
            if "503" in msg or "UNAVAILABLE" in msg or "429" in msg:
                time.sleep(1.5)

                try:
                    resp = self._client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "temperature": 0,
                        },
                    )

                    return _extract_json(resp.text or "")
                except Exception as e2:
                    self.last_error = model + ": " + str(e2)[:300]

            return None


def _unique(seq):
    seen = set()
    out = []

    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    return out
