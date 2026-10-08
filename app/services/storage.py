import os
from abc import ABC, abstractmethod
from typing import Optional

from app.core.config import settings
from app.core.logging import logger


class StorageProvider(ABC):
    """Abstract interface for storage providers (Local FS, AWS S3, Google Cloud Storage, etc.)."""

    @abstractmethod
    def save_file(self, relative_path: str, data: bytes) -> str:
        """Save raw bytes to relative path and return file path reference."""
        pass

    @abstractmethod
    def get_file(self, relative_path: str) -> bytes:
        """Retrieve raw file bytes from relative path."""
        pass

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Check if file exists."""
        pass

    @abstractmethod
    def delete_file(self, relative_path: str) -> bool:
        """Delete file at relative path."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local File System Implementation of StorageProvider."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or settings.STORAGE_DIR)
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve_path(self, relative_path: str) -> str:
        # Prevent path traversal attacks
        clean_rel = os.path.normpath(relative_path).lstrip("/\\")
        abs_path = os.path.abspath(os.path.join(self.base_dir, clean_rel))
        if not abs_path.startswith(self.base_dir):
            raise ValueError(f"Path traversal detected: {relative_path}")
        return abs_path

    def save_file(self, relative_path: str, data: bytes) -> str:
        abs_path = self._resolve_path(relative_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(data)
        return relative_path

    def get_file(self, relative_path: str) -> bytes:
        abs_path = self._resolve_path(relative_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"File not found: {relative_path}")
        with open(abs_path, "rb") as f:
            return f.read()

    def exists(self, relative_path: str) -> bool:
        try:
            abs_path = self._resolve_path(relative_path)
            return os.path.isfile(abs_path)
        except ValueError:
            return False

    def delete_file(self, relative_path: str) -> bool:
        try:
            abs_path = self._resolve_path(relative_path)
            if os.path.isfile(abs_path):
                os.remove(abs_path)
                return True
            return False
        except Exception as e:
            logger.warning(f"Error deleting file {relative_path}: {e}")
            return False


# Singleton default storage instance
storage_provider = LocalStorageProvider()


def get_storage_provider() -> StorageProvider:
    """Dependency injection helper for StorageProvider."""
    return storage_provider
