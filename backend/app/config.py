from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    contact_email: str = "you@example.com"
    gemini_api_key: str = ""

    # Preferred Gemini model. If it is unavailable, LLM.py resolves a
    # working flash model from the API's model list at runtime instead of
    # silently giving up.
    gemini_model: str = "gemini-flash-lite-latest"
    gemini_fallback_models: str = "gemini-3.5-flash,gemini-3.1-flash-lite"

    openalex_api_key: str = ""

    db_path: str = "prooftrace.db"

    # How many citations to fully verify. The bibliography is always
    # parsed in full; this only caps the number of API/LLM lookups.
    # Raised from 50 to 200 so a normal reference list is checked in
    # full rather than silently cut off.
    max_citations: int = 200

    http_timeout: float = 20.0
    cache_ttl_hours: int = 24

    # Retraction data changes over time, so it is cached for much less
    # than ordinary metadata. The report also records when each check
    # ran, so a stale result is visible rather than implied current.
    retraction_cache_ttl_hours: int = 6

    # Hard ceiling on pasted text / extracted PDF text. Large enough that
    # a bibliography at the end of a normal paper is never truncated.
    max_input_chars: int = 300000
    max_pdf_pages: int = 80

    # Full-text mode. When on, the Evidence Analyst reads the open-access
    # full text of a matched paper (Europe PMC JATS XML first, then an
    # OpenAlex open-access PDF) instead of only its abstract. This lets a
    # claim be VERIFIED even when no abstract was indexed, and gives the
    # model the whole argument rather than a summary. Turn it off to keep
    # every run abstract-only and faster.
    full_text_mode: bool = True
    max_full_text_chars: int = 20000
    max_fulltext_pages: int = 30
    max_fulltext_bytes: int = 8 * 1024 * 1024

    # Seconds to wait for a single Gemini call before falling back.
    llm_timeout: float = 45.0

    cors_origins: str = "http://localhost:5173"

    @property
    def gemini_fallbacks(self) -> list[str]:
        return [
            m.strip()
            for m in self.gemini_fallback_models.split(",")
            if m.strip()
        ]


settings = Settings()
