"""Lightweight symmetric encryption for stored FPL credentials.

Uses Fernet from cryptography. The key must be provided via the
FPL_CREDENTIALS_KEY env var or backend.secrets.fernet_key in secrets.toml.
"""
import base64
import json
import os

from cryptography.fernet import Fernet

from backend import config


def _get_key() -> bytes:
    key = config.FPL_CREDENTIALS_KEY
    if not key:
        raise RuntimeError("FPL_CREDENTIALS_KEY is not configured")
    return key.encode("utf-8") if isinstance(key, str) else key


def encrypt_text(plain_text: str) -> str:
    f = Fernet(_get_key())
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_text(cipher_text: str) -> str:
    f = Fernet(_get_key())
    return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")


def encrypt_dict(data: dict) -> str:
    return encrypt_text(json.dumps(data, default=str))


def decrypt_dict(cipher_text: str) -> dict:
    return json.loads(decrypt_text(cipher_text))
