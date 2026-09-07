import os
from dotenv import load_dotenv

# Load environment variables from .env file (if exists)
load_dotenv()


def _is_production() -> bool:
    return os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}


def get_env_var(key: str, required: bool = True) -> str:
    """
    Get an environment variable, failing fast if required and missing.
    """
    value = os.getenv(key)
    if required and not value:
        raise ValueError(f"CRITICAL ERROR: Required environment variable '{key}' is missing or empty.")
    return value or ""


class Settings:
    @property
    def openrouter_api_key(self) -> str:
        return get_env_var("OPENROUTER_API_KEY", required=True)

    @property
    def openrouter_model(self) -> str:
        return os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    @property
    def openrouter_fallback_models(self) -> list[str]:
        raw = os.getenv("OPENROUTER_FALLBACK_MODELS", "openai/gpt-4o-mini,openai/gpt-4o")
        models = []
        for entry in raw.split(","):
            model = entry.strip()
            if model:
                models.append(model)
        return models

    @property
    def groq_api_key(self) -> str:
        # Kept for compatibility with existing callers; new AI calls use OpenRouter.
        return get_env_var("GROQ_API_KEY", required=True)

    @property
    def wp_url(self) -> str:
        return get_env_var("WP_URL", required=True)

    @property
    def wp_username(self) -> str:
        return get_env_var("WP_USERNAME", required=True)

    @property
    def wp_app_password(self) -> str:
        return get_env_var("WP_APP_PASSWORD", required=True)

    @property
    def casino_data_api_key(self) -> str:
        return get_env_var("CASINO_DATA_API_KEY", required=True)

    @property
    def discovery_sources(self) -> list:
        # Configurable list of official discovery sources
        return [
            "https://www.pragmaticplay.com/en/news/",
            "https://www.playngo.com/news",
            "https://netent.com/en/news/",
            "https://relax-gaming.com/news",
            "https://www.hacksawgaming.com/news",
            "https://firstlookgames.com/releases" # If available
        ]
        

# Global settings instance
settings = Settings()
