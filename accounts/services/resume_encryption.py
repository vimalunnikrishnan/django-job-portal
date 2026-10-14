import os

from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured


def get_fernet():
    key = os.getenv("RESUME_ENCRYPTION_KEY")

    if not key:
        raise ImproperlyConfigured(
            "RESUME_ENCRYPTION_KEY is not configured."
        )

    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise ImproperlyConfigured(
            "RESUME_ENCRYPTION_KEY is invalid."
        )


def encrypt_resume(file_content: bytes) -> bytes:
    return get_fernet().encrypt(file_content)


def decrypt_resume(encrypted_content: bytes) -> bytes:
    try:
        return get_fernet().decrypt(encrypted_content)
    except InvalidToken as exc:
        raise ValueError(
            "Resume decryption failed. Check the encryption key "
            "and encrypted file integrity."
        ) from exc