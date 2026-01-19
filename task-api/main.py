"""
Task Management API - Complete CRUD Implementation.

A production-ready REST API for task management with:
- Create: POST /tasks
- Read: GET /tasks and GET /tasks/{task_id}
- Update: PUT /tasks/{task_id}
- Delete: DELETE /tasks/{task_id}

Technologies:
- FastAPI: Web framework with automatic documentation
- SQLModel: Combines SQLAlchemy ORM with Pydantic validation
- PostgreSQL (Neon): Cloud-hosted database
- pytest: Testing framework

The API includes:
1. Automatic data validation (Pydantic)
2. Type hints throughout
3. Automatic API documentation (Swagger UI)
4. Proper HTTP status codes and error handling
5. Database persistence with SQLModel/SQLAlchemy
"""

from fastapi import FastAPI, Depends, HTTPException, status
from sqlmodel import Session, select
from datetime import datetime

from config import get_settings
from database import create_db_and_tables, get_session, engine
from models import Task, TaskCreate, TaskUpdate, TaskResponse

# Get settings
settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    description="RESTful API for managing tasks with full CRUD operations",
    version=settings.api_version,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc documentation
)


# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
def on_startup():
    """Create database tables on application startup.

    This event runs once when the FastAPI application starts.
    It ensures all required tables exist before any requests are processed.
    """
    print("[*] Starting Task Management API...")
    print(f"[DB] Database: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'Not configured'}")
    create_db_and_tables()
    print("[OK] API ready to accept requests")


@app.on_event("shutdown")
def on_shutdown():
    """Clean up resources on application shutdown."""
    print("[!] Shutting down Task Management API...")


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.get("/", tags=["Health"])
def root():
    """Root endpoint - health check.

    Returns:
        dict: API status and information
    """
    return {
        "status": "ok",
        "message": "Task Management API is running",
        "api_version": settings.api_version,
        "docs_url": "/docs"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status with timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# CREATE ENDPOINT - POST /tasks
# ============================================================================

@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tasks"],
    summary="Create a new task",
    responses={
        201: {"description": "Task created successfully"},
        422: {"description": "Validation error in request body"},
    }
)
def create_task(
    task: TaskCreate,
    session: Session = Depends(get_session)
) -> TaskResponse:
    """Create a new task in the database.

    This endpoint:
    1. Validates the incoming JSON with TaskCreate model (Pydantic validation)
    2. Creates a new Task database record
    3. Commits to PostgreSQL database
    4. Returns the created task with auto-generated ID and timestamps

    Args:
        task: Task data from request body (validated by Pydantic)
        session: Database session (injected by FastAPI)

    Returns:
        TaskResponse: The created task with ID and timestamps

    Raises:
        422 Unprocessable Entity: If validation fails (e.g., invalid status)

    Example:
        POST /tasks
        Content-Type: application/json

        {
            "title": "Learn FastAPI",
            "description": "Complete the tutorial",
            "status": "pending",
            "priority": 2
        }

        Response (201 Created):
        {
            "id": 1,
            "title": "Learn FastAPI",
            "description": "Complete the tutorial",
            "status": "pending",
            "priority": 2,
            "created_at": "2024-01-19T10:30:00",
            "updated_at": "2024-01-19T10:30:00"
        }
    """
    # Create new database object from the request data
    db_task = Task.from_orm(task)

    # Add to session (stage in memory)
    session.add(db_task)

    # Commit to database (write to PostgreSQL)
    session.commit()

    # Refresh to get auto-generated ID and timestamps
    session.refresh(db_task)

    return db_task


# ============================================================================
# READ ENDPOINTS - GET /tasks and GET /tasks/{task_id}
# ============================================================================

@app.get(
    "/tasks",
    response_model=list[TaskResponse],
    tags=["Tasks"],
    summary="List all tasks",
    responses={
        200: {"description": "List of tasks"},
    }
)
def list_tasks(
    skip: int = 0,
    limit: int = 100,
    status_filter: str = None,
    session: Session = Depends(get_session)
) -> list[TaskResponse]:
    """Retrieve all tasks with optional filtering.

    This endpoint:
    1. Queries the database for all tasks
    2. Supports pagination with skip/limit
    3. Supports filtering by status

    Args:
        skip: Number of tasks to skip (for pagination)
        limit: Maximum number of tasks to return (default 100)
        status_filter: Optional filter by status (pending, in_progress, completed)
        session: Database session (injected)

    Returns:
        list[TaskResponse]: List of tasks

    Example - Get all tasks:
        GET /tasks
        Response (200 OK):
        [
            {"id": 1, "title": "Learn FastAPI", ...},
            {"id": 2, "title": "Learn SQLModel", ...}
        ]

    Example - Paginate results:
        GET /tasks?skip=0&limit=10

    Example - Filter by status:
        GET /tasks?status_filter=pending
    """
    # Build query
    statement = select(Task)

    # Apply status filter if provided
    if status_filter:
        statement = statement.where(Task.status == status_filter)

    # Execute query with pagination
    tasks = session.exec(
        statement.offset(skip).limit(limit)
    ).all()

    return tasks


@app.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["Tasks"],
    summary="Get a specific task",
    responses={
        200: {"description": "Task found"},
        404: {"description": "Task not found"},
    }
)
def read_task(
    task_id: int,
    session: Session = Depends(get_session)
) -> TaskResponse:
    """Retrieve a specific task by ID.

    Args:
        task_id: Task ID (from URL path)
        session: Database session (injected)

    Returns:
        TaskResponse: The requested task

    Raises:
        HTTPException 404: If task doesn't exist

    Example:
        GET /tasks/1
        Response (200 OK):
        {
            "id": 1,
            "title": "Learn FastAPI",
            "description": "Complete the tutorial",
            "status": "pending",
            "priority": 2,
            "created_at": "2024-01-19T10:30:00",
            "updated_at": "2024-01-19T10:30:00"
        }
    """
    # Query database for task
    task = session.get(Task, task_id)

    # Return 404 if not found
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )

    return task


# ============================================================================
# UPDATE ENDPOINT - PUT /tasks/{task_id}
# ============================================================================

@app.put(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["Tasks"],
    summary="Update a task",
    responses={
        200: {"description": "Task updated successfully"},
        404: {"description": "Task not found"},
        422: {"description": "Validation error in request body"},
    }
)
def update_task(
    task_id: int,
    task_update: TaskUpdate,
    session: Session = Depends(get_session)
) -> TaskResponse:
    """Update an existing task.

    This endpoint:
    1. Finds the existing task by ID
    2. Updates only the provided fields
    3. Saves changes to database
    4. Returns updated task

    Args:
        task_id: Task ID to update (from URL)
        task_update: Fields to update (from request body)
        session: Database session (injected)

    Returns:
        TaskResponse: Updated task

    Raises:
        HTTPException 404: If task doesn't exist
        422 Unprocessable Entity: If validation fails

    Example - Update status only:
        PUT /tasks/1
        {
            "status": "in_progress"
        }
        # title, description, priority remain unchanged

    Example - Update multiple fields:
        PUT /tasks/1
        {
            "title": "New Title",
            "status": "completed",
            "priority": 3
        }
    """
    # Find existing task
    db_task = session.get(Task, task_id)

    # Return 404 if not found
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )

    # Get update data (only fields that were explicitly provided)
    update_data = task_update.dict(exclude_unset=True)

    # Update the task object with new data
    for field, value in update_data.items():
        setattr(db_task, field, value)

    # Update the updated_at timestamp
    db_task.updated_at = datetime.utcnow()

    # Save to database
    session.add(db_task)
    session.commit()
    session.refresh(db_task)

    return db_task


# ============================================================================
# DELETE ENDPOINT - DELETE /tasks/{task_id}
# ============================================================================

@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Tasks"],
    summary="Delete a task",
    responses={
        204: {"description": "Task deleted successfully"},
        404: {"description": "Task not found"},
    }
)
def delete_task(
    task_id: int,
    session: Session = Depends(get_session)
):
    """Delete a task from the database.

    This endpoint:
    1. Finds the task by ID
    2. Deletes it from the database
    3. Returns 204 No Content (empty response)

    Args:
        task_id: Task ID to delete (from URL)
        session: Database session (injected)

    Raises:
        HTTPException 404: If task doesn't exist

    Returns:
        None (status 204)

    Example:
        DELETE /tasks/1
        Response (204 No Content): [empty body]

        Subsequent GET /tasks/1 returns 404
    """
    # Find the task
    task = session.get(Task, task_id)

    # Return 404 if not found
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )

    # Delete from database
    session.delete(task)

    # Commit deletion
    session.commit()

    # 204 No Content - no return needed


# ============================================================================
# STATS ENDPOINT - GET /stats
# ============================================================================

@app.get(
    "/stats",
    tags=["Analytics"],
    summary="Get task statistics"
)
def get_stats(session: Session = Depends(get_session)):
    """Get statistics about tasks.

    Returns counts of tasks by status.

    Args:
        session: Database session (injected)

    Returns:
        dict: Task counts by status

    Example:
        GET /stats
        Response (200 OK):
        {
            "total": 5,
            "pending": 2,
            "in_progress": 2,
            "completed": 1
        }
    """
    # Count tasks by status
    total = session.exec(select(Task)).all()
    pending = session.exec(
        select(Task).where(Task.status == "pending")
    ).all()
    in_progress = session.exec(
        select(Task).where(Task.status == "in_progress")
    ).all()
    completed = session.exec(
        select(Task).where(Task.status == "completed")
    ).all()

    return {
        "total": len(total),
        "pending": len(pending),
        "in_progress": len(in_progress),
        "completed": len(completed)
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
