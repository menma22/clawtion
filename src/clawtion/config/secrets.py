"""Secrets management for clawtion.

Implements a tiered secrets store with the following priority:
1. Environment variable (CLAWTION_GEMINI_API_KEY, etc.)
2. OS keychain via the *keyring* library
3. Encrypted file fallback (~/.clawtion/secrets.enc)
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

_SECRETS_DIR = Path.home() / ".clawtion"
_SECRETS_FILE = _SECRETS_DIR / "secrets.enc"

# Environment variable names for each well-known secret
_ENV_MAP: dict[str, str] = {
    "gemini_api_key": "CLAWTION_GEMINI_API_KEY",
    "claude_api_key": "CLAWTION_CLAUDE_API_KEY",
    "openai_api_key": "CLAWTION_OPENAI_API_KEY",
}

_KEYRING_SERVICE = "clawtion"


# ---------------------------------------------------------------------------
# Encrypted file helpers
# ---------------------------------------------------------------------------


def _ensure_secrets_dir() -> None:
    _SECRETS_DIR.mkdir(parents=True, exist_ok=True)


def _derive_key() -> bytes:
    """Derive a 32-byte Fernet key from machine-local identity.

    Uses a SHA-256 hash of (hostname + username) as a deterministic but
    machine-bound key. This is NOT cryptographically strong — it is a
    convenience fallback for the encrypted file tier.
    """
    import hashlib

    if hasattr(os, "uname"):
        raw = f"{os.uname().nodename}-{os.getlogin()}"
    else:
        raw = os.environ.get("COMPUTERNAME", "unknown")
    return hashlib.sha256(raw.encode()).digest()


def _read_encrypted_file() -> dict[str, Any]:
    """Read and decrypt the secrets file, returning the stored dict."""
    from cryptography.fernet import Fernet

    if not _SECRETS_FILE.exists():
        return {}

    key = _derive_key()
    cipher = Fernet(_bytes_to_b64_key(key))
    try:
        raw = _SECRETS_FILE.read_bytes()
        decrypted = cipher.decrypt(raw)
        return dict(json.loads(decrypted.decode("utf-8")))
    except Exception:
        return {}


def _write_encrypted_file(data: dict[str, Any]) -> None:
    """Encrypt and write the secrets dict to the file."""
    from cryptography.fernet import Fernet

    _ensure_secrets_dir()
    key = _derive_key()
    cipher = Fernet(_bytes_to_b64_key(key))
    payload = json.dumps(data).encode("utf-8")
    encrypted = cipher.encrypt(payload)
    _SECRETS_FILE.write_bytes(encrypted)
    _SECRETS_FILE.chmod(0o600)


def _bytes_to_b64_key(raw: bytes) -> bytes:
    """Convert arbitrary 32 bytes to a URL-safe base64-encoded Fernet key."""
    import base64

    return base64.urlsafe_b64encode(raw.ljust(32, b"\0")[:32])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_secret(key: str) -> str | None:
    """Retrieve a secret by name.

    Checks (in order):
    1. The corresponding CLAWTION_* environment variable
    2. The OS keychain (via *keyring*)
    3. The encrypted fallback file

    Args:
        key: Secret name, e.g. "gemini_api_key", "claude_api_key".

    Returns:
        The secret value, or None if not found anywhere.
    """
    # 1. Environment variable
    env_var = _ENV_MAP.get(key)
    if env_var:
        value = os.environ.get(env_var)
        if value:
            return value

    # 2. OS keychain
    try:
        import keyring

        value = keyring.get_password(_KEYRING_SERVICE, key)
        if value:
            return value
    except Exception:
        pass

    # 3. Encrypted file fallback
    data = _read_encrypted_file()
    value = data.get(key)
    if isinstance(value, str):
        return value

    return None


def set_secret(key: str, value: str) -> None:
    """Store a secret.

    Attempts the OS keychain first; falls back to the encrypted file.

    Args:
        key:   Secret name, e.g. "gemini_api_key".
        value: The secret value to store.
    """
    # 1. OS keychain
    try:
        import keyring

        keyring.set_password(_KEYRING_SERVICE, key, value)
        return
    except Exception:
        pass

    # 2. Encrypted file fallback
    data = _read_encrypted_file()
    data[key] = value
    _write_encrypted_file(data)


def delete_secret(key: str) -> None:
    """Remove a stored secret from all tiers.

    Args:
        key: Secret name to delete, e.g. "gemini_api_key".
    """
    # 1. OS keychain
    try:
        import keyring

        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(_KEYRING_SERVICE, key)
    except Exception:
        pass

    # 2. Encrypted file fallback
    data = _read_encrypted_file()
    data.pop(key, None)
    _write_encrypted_file(data)
