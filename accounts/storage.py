from django.core.files.base import ContentFile
from storages.backends.s3 import S3Storage

from accounts.services.resume_encryption import (
    encrypt_resume,
    decrypt_resume,
)


class EncryptedResumeStorage(S3Storage):
    """
    Store encrypted resumes in private S3 storage.
    Decrypt resumes when they are opened through Django.
    """

    ENCRYPTION_MARKER = b"RESUME_ENCRYPTED_V1:"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default_acl", None)
        kwargs.setdefault("querystring_auth", True)
        kwargs.setdefault("file_overwrite", False)
        super().__init__(*args, **kwargs)

    def _save(self, name, content):
        original_content = content.read()
        encrypted_content = (
            self.ENCRYPTION_MARKER
            + encrypt_resume(original_content)
        )

        return super()._save(
            name,
            ContentFile(encrypted_content),
        )

    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError(
                "Encrypted resumes can only be opened in read mode."
            )

        file = super()._open(name, mode)

        try:
            content = file.read()
        finally:
            file.close()

        if content.startswith(self.ENCRYPTION_MARKER):
            encrypted_content = content[
                len(self.ENCRYPTION_MARKER):
            ]
            content = decrypt_resume(encrypted_content)

        return ContentFile(content, name=name)