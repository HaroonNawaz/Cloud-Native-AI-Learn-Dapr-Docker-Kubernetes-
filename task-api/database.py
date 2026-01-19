"""
Database connection and session management.

This module handles:
1. Creating the database engine (connection pool manager)
2. Providing sessions through dependency injection
3. Creating database tables on startup

The engine is the bridge between Python code and PostgreSQL database.
Sessions are conversations with the database.
"""

from sqlmodel import SQLModel, create_engine, Session
from config import get_settings

# Get settings (loaded from .env file)
settings = get_settings()

# Create database engine
# The engine manages connections to PostgreSQL through a connection pool
engine = create_engine(
    settings.database_url,
    echo=settings.debug,  # Print SQL queries if DEBUG=true
    pool_pre_ping=True,  # Test connections before using them
)


def create_db_and_tables():
    """Create all database tables based on SQLModel definitions.

    This function:
    1. Inspects all SQLModel classes (models with table=True)
    2. Creates corresponding tables in PostgreSQL if they don't exist
    3. Is safe to call multiple times (idempotent)

    Called on application startup via @app.on_event("startup")

    Raises:
        Exception: If database connection fails

    Note:
        For production apps, use Alembic migrations instead of create_all()
        This approach works for development but doesn't handle schema evolution well.
    """
    try:
        SQLModel.metadata.create_all(engine)
        print("[OK] Database tables created successfully")
    except Exception as e:
        print(f"[ERROR] Database error: {e}")
        raise


def get_session():
    """Dependency function to provide database sessions to endpoints.

    This is a FastAPI dependency that:
    1. Creates a database session before the endpoint runs
    2. Yields it to the endpoint for use
    3. Automatically closes it after the endpoint completes

    The 'yield' statement is crucial:
    - Code before yield: Runs BEFORE endpoint (setup)
    - Endpoint: Runs while session is active
    - Code after yield: Runs AFTER endpoint (cleanup/teardown)

    Used in endpoints via: session: Session = Depends(get_session)

    Yields:
        Session: Active database session for one request

    Example:
        @app.get("/tasks")
        def list_tasks(session: Session = Depends(get_session)):
            # session is automatically provided
            tasks = session.exec(select(Task)).all()
            return tasks
            # session is automatically closed after this function returns
    """
    with Session(engine) as session:
        yield session
        # Session automatically closes after endpoint completes
