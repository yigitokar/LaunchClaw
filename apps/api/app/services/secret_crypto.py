from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.config import settings

SECRET_CIPHERTEXT_PREFIX = "fernet::"


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def secret_encryption_configured() -> bool:
    return bool(settings.secret_encryption_key.strip())


def _cipher() -> Fernet:
    key = settings.secret_encryption_key.strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail=_detail("secrets_unavailable", "Secret encryption is not configured"),
        )

    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=_detail("secrets_unavailable", "Secret encryption key is invalid"),
        ) from exc


def secret_value_needs_migration(value: str | None) -> bool:
    return bool(value) and not value.startswith(SECRET_CIPHERTEXT_PREFIX)


def encrypt_secret_value(value: str) -> str:
    token = _cipher().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{SECRET_CIPHERTEXT_PREFIX}{token}"


def decrypt_secret_value(value: str) -> str:
    if not value.startswith(SECRET_CIPHERTEXT_PREFIX):
        return value

    token = value.removeprefix(SECRET_CIPHERTEXT_PREFIX)
    try:
        return _cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as exc:  # pragma: no cover - invalid ciphertext should surface at runtime
        raise HTTPException(
            status_code=502,
            detail=_detail("secret_decryption_failed", "Stored secret value could not be decrypted"),
        ) from exc
