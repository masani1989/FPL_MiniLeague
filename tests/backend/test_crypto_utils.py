import os

import pytest
from cryptography.fernet import Fernet

from backend import crypto_utils, config


@pytest.fixture
def set_credentials_key(monkeypatch):
    # Fernet keys must be 32 url-safe base64-encoded bytes.
    monkeypatch.setattr(config, "FPL_CREDENTIALS_KEY", Fernet.generate_key().decode("utf-8"), raising=False)


def test_encrypt_decrypt_text(set_credentials_key):
    plain = "my_secret_password"
    cipher = crypto_utils.encrypt_text(plain)
    assert cipher != plain
    assert crypto_utils.decrypt_text(cipher) == plain


def test_encrypt_decrypt_cookie_string(set_credentials_key):
    cookie = "pl_profile=abc123; _ga=xyz"
    cipher = crypto_utils.encrypt_text(cookie)
    assert isinstance(cipher, str)
    decrypted = crypto_utils.decrypt_text(cipher)
    assert decrypted == cookie


def test_missing_key_raises(monkeypatch):
    monkeypatch.setattr(config, "FPL_CREDENTIALS_KEY", "", raising=False)
    with pytest.raises(RuntimeError):
        crypto_utils.encrypt_text("x")
