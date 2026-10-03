"""Domain exceptions."""


class TranslationError(Exception):
    """Raised when translation fails."""


class NotificationDeliveryError(RuntimeError):
    """Raised when the notification adapter cannot deliver a message."""
