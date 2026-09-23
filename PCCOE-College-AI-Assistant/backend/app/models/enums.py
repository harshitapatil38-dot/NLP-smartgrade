import enum

class RoleEnum(str, enum.Enum):
    """
    Role hierarchy for authorization:
    - SUPER_ADMIN: Full system control.
    - DEPARTMENT_ADMIN: Can manage content/users for their department.
    - CONTENT_ADMIN: General content manager.
    - ADMIN: Basic administrative role (Step 7A/7B).
    - FACULTY: Faculty member role (Step 7B).
    - STAFF: Basic staff role (Step 7A).
    """
    SUPER_ADMIN = "SUPER_ADMIN"
    DEPARTMENT_ADMIN = "DEPARTMENT_ADMIN"
    CONTENT_ADMIN = "CONTENT_ADMIN"
    ADMIN = "ADMIN"
    FACULTY = "FACULTY"
    STAFF = "STAFF"

class StatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

class ProcessingStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

