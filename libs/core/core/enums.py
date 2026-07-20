import enum


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    READ_ONLY = "read_only"


class DocumentStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class OAuthProvider(enum.StrEnum):
    GOOGLE = "google"
    GITHUB = "github"


class MessageRole(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
