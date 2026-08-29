from collections.abc import Mapping
from typing import Any


class SnakktilmegError(Exception):
    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.context = context

    def log_context(self) -> Mapping[str, Any]:
        return {
            "error_type": type(self).__name__,
            "error": str(self),
            **self.context,
        }


class RecordingError(SnakktilmegError):
    pass


class TranscriptionError(SnakktilmegError):
    pass


class TextInsertionError(SnakktilmegError):
    pass


class HotkeyError(SnakktilmegError):
    pass


class IndicatorError(SnakktilmegError):
    pass


class ConfigurationError(SnakktilmegError):
    pass
