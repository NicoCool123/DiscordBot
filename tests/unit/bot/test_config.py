import os
import pytest
from unittest.mock import patch


class TestBotConfig:
    """Tests for bot configuration loading."""

    @pytest.fixture(autouse=True)
    def clean_env(self, monkeypatch):
        # Entfernt alle Umgebungsvariablen, die Settings beeinflussen könnten
        keys = [
            "DEBUG",
            "DISCORD_PREFIX",
            "API_URL",
            "RCON_ENABLED",
            "LOG_LEVEL",
            "LOG_FORMAT",
            "DATABASE_URL",
        ]
        for key in keys:
            monkeypatch.delenv(key, raising=False)

        # .env Datei vollständig deaktivieren
        monkeypatch.setenv("Pydantic_env_file", "")

    def test_config_loads_from_env(self):
        env = {
            "DISCORD_TOKEN": "test-token",
            "BOT_API_KEY": "test-api-key",
            "DISCORD_PREFIX": ">>",
            "API_URL": "http://api:8000",
            "DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            from bot.config import BotSettings

            settings = BotSettings(
                discord_token="test-token",
                bot_api_key="test-api-key",
            )

            assert settings.discord_token == "test-token"
            assert settings.bot_api_key == "test-api-key"

    def test_config_defaults(self):
        from bot.config import BotSettings

        settings = BotSettings(
            discord_token="test-token",
            bot_api_key="test-api-key",
        )

        assert settings.discord_prefix == "!"
        assert settings.api_url == "http://localhost:8000"
        assert settings.debug is False
        assert settings.rcon_enabled is False

    def test_is_production_property(self):
        from bot.config import BotSettings

        settings = BotSettings(
            discord_token="test-token",
            bot_api_key="test-api-key",
            debug=False,
        )
        assert settings.is_production is True

        settings_debug = BotSettings(
            discord_token="test-token",
            bot_api_key="test-api-key",
            debug=True,
        )
        assert settings_debug.is_production is False