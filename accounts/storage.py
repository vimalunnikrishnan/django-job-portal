from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

from accounts.services.resume_encryption import (
    encrypt_resume,
    decrypt_resume,
)


class EncryptedResumeStorage(FileSystemStorage):
    """
    Encrypt resume contents before saving them.
    Decrypt encrypted resumes when they are opened.
    """

    ENCRYPTION_MARKER = b"RESUME_ENCRYPTED_V1:"

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
        file = super()._open(name, mode)

        if mode != "rb":
            file.close()
            raise ValueError(
                "Encrypted resumes can only be opened in read mode."
            )

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