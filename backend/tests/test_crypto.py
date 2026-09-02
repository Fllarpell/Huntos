from cryptography.fernet import Fernet

from app.config import settings
from app.services.crypto import reset_fernet_cache, seal, unseal


def test_seal_is_identity_without_key() -> None:
    settings.token_fernet_key = ""
    reset_fernet_cache()
    assert seal("plain-token") == "plain-token"
    assert unseal("plain-token") == "plain-token"


def test_seal_roundtrip_and_idempotent() -> None:
    key = Fernet.generate_key().decode()
    settings.token_fernet_key = key
    reset_fernet_cache()
    try:
        cipher = seal("refresh-token-value")
        assert cipher is not None and cipher.startswith("gAAAA")
        assert cipher != "refresh-token-value"
        assert unseal(cipher) == "refresh-token-value"
        assert seal(cipher) == cipher
    finally:
        settings.token_fernet_key = ""
        reset_fernet_cache()


def test_llm_config_unseals_openai_key() -> None:
    from types import SimpleNamespace

    from app.services.scoring.llm import config_from_profile

    key = Fernet.generate_key().decode()
    settings.token_fernet_key = key
    reset_fernet_cache()
    try:
        profile = SimpleNamespace(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            openai_api_key=seal("sk-test-secret"),
            ollama_base_url="http://127.0.0.1:11434",
        )
        cfg = config_from_profile(profile)  # type: ignore[arg-type]
        assert cfg.openai_api_key == "sk-test-secret"
    finally:
        settings.token_fernet_key = ""
        reset_fernet_cache()


def test_runs_scheduler_roles() -> None:
    prev_env, prev_role = settings.app_env, settings.app_role
    try:
        settings.app_env = "prod"
        settings.app_role = "api"
        assert settings.runs_scheduler() is False
        settings.app_role = "worker"
        assert settings.runs_scheduler() is True
        settings.app_role = "all"
        assert settings.runs_scheduler() is True
        settings.app_env = "test"
        assert settings.runs_scheduler() is False
    finally:
        settings.app_env = prev_env
        settings.app_role = prev_role
