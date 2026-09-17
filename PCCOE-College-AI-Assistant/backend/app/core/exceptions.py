class KnowledgeBaseException(Exception):
    """Base exception for knowledge base operations."""
    pass

class InvalidStatusTransitionError(KnowledgeBaseException):
    """Raised when an invalid status transition is attempted."""
    pass

class ResourceNotFoundError(KnowledgeBaseException):
    """Raised when a requested resource is not found."""
    pass
