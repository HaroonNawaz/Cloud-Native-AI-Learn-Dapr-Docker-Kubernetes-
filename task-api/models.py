"""
SQLModel task model definitions.

This module defines the Task model that represents both:
1. A database table (when table=True)
2. A Pydantic validation model

The model uses SQLModel to combine SQLAlchemy ORM with Pydantic validation.
"""

from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class TaskBase(SQLModel):
    """Base Task model with common fields.

    This is the foundation for both database and API models.
    By extracting common fields, we avoid duplication.

    Attributes:
        title: Task title (required, indexed for fast lookup)
        description: Detailed task description (optional)
        status: Current task status - "pending", "in_progress", or "completed"
        priority: Priority level: 1 (low), 2 (medium), 3 (high)
    """

    title: str = Field(index=True, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: str = Field(
        default="pending",
        regex="^(pending|in_progress|completed)$"
    )
    priority: int = Field(default=1, ge=1, le=3)


class Task(TaskBase, table=True):
    """Task database model.

    The 'table=True' parameter tells SQLModel to:
    1. Create this as a database table
    2. Treat instances as database records

    Automatically managed fields:
    - id: Auto-incremented primary key
    - created_at: Set when record is first created
    - updated_at: Updated whenever record changes

    Example:
        >>> task = Task(title="Learn FastAPI", description="Complete tutorial")
        >>> # When saved to database, id, created_at, updated_at are auto-set
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TaskCreate(TaskBase):
    """Model for creating new tasks.

    This model is used in POST requests to validate client input.
    Clients should send this structure in the request body.

    Fields:
        title: Required - task title
        description: Optional - task description
        status: Optional - defaults to "pending"
        priority: Optional - defaults to 1 (low)

    Example:
        POST /tasks
        {
            "title": "Buy groceries",
            "description": "Milk, eggs, bread",
            "status": "pending",
            "priority": 2
        }
    """

    pass


class TaskUpdate(SQLModel):
    """Model for updating tasks.

    All fields are optional - only provided fields are updated.
    This allows partial updates (e.g., only change status without changing priority).

    Attributes:
        title: Optional new title
        description: Optional new description
        status: Optional new status
        priority: Optional new priority

    Example:
        PUT /tasks/1
        {
            "status": "in_progress",
            "priority": 3
        }
        # Only status and priority change; others remain unchanged
    """

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(
        None,
        regex="^(pending|in_progress|completed)$"
    )
    priority: Optional[int] = Field(None, ge=1, le=3)


class TaskResponse(TaskBase):
    """Model for task responses.

    This model is used in GET requests to define what fields clients receive.
    The 'response_model' parameter in FastAPI uses this to filter output.

    It includes all fields from TaskBase plus database-managed fields.

    Attributes:
        id: Auto-generated task ID
        created_at: When task was created
        updated_at: When task was last modified

    Example:
        GET /tasks/1 response:
        {
            "id": 1,
            "title": "Learn FastAPI",
            "description": "Complete tutorial",
            "status": "in_progress",
            "priority": 2,
            "created_at": "2024-01-19T10:30:00",
            "updated_at": "2024-01-19T14:45:00"
        }
    """

    id: int
    created_at: datetime
    updated_at: datetime
