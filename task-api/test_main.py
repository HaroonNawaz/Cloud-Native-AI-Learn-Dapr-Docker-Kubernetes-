"""
Test suite for Task Management API.

Tests all CRUD operations with an in-memory SQLite database.
Each test gets a fresh database to avoid test pollution.

To run:
    pytest test_main.py -v
    pytest test_main.py::test_create_task -v  # Single test
    pytest test_main.py -v --tb=short  # Shorter error messages

Coverage:
    pytest --cov=. test_main.py
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from main import app, get_session
from models import Task


# ============================================================================
# FIXTURES - Setup/Teardown for Each Test
# ============================================================================

@pytest.fixture(name="session")
def session_fixture():
    """Create fresh in-memory database for each test.

    This fixture:
    1. Creates an in-memory SQLite database (fast, no file I/O)
    2. Creates all tables
    3. Provides the session to the test
    4. Automatically closes after test completes

    Using in-memory database ensures:
    - Tests run fast (no disk I/O)
    - Tests are isolated (fresh DB each time)
    - No conflicts with production database
    - No need to clean up test data
    """
    engine = create_engine(
        "sqlite://",  # In-memory SQLite
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create FastAPI test client with test database.

    This fixture:
    1. Takes the session fixture as input
    2. Overrides FastAPI's get_session dependency to use test database
    3. Creates test client for making requests
    4. Cleans up after test

    This ensures API tests use the test database, not production.
    """

    def get_session_override():
        return session

    # Override the dependency
    app.dependency_overrides[get_session] = get_session_override

    # Create test client
    client = TestClient(app)

    yield client

    # Cleanup
    app.dependency_overrides.clear()


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

def test_read_root(client: TestClient):
    """Test root endpoint returns API status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "api_version" in data
    assert "docs_url" in data


def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


# ============================================================================
# CREATE TESTS - POST /tasks
# ============================================================================

def test_create_task(client: TestClient):
    """Test creating a new task with all fields.

    Steps:
    1. Send POST request with valid task data
    2. Verify 201 Created status code
    3. Verify all fields are present in response
    4. Verify auto-generated fields (id, created_at, updated_at)
    """
    response = client.post(
        "/tasks",
        json={
            "title": "Learn FastAPI",
            "description": "Complete the FastAPI tutorial",
            "status": "pending",
            "priority": 2
        }
    )

    assert response.status_code == 201
    data = response.json()

    # Verify sent fields
    assert data["title"] == "Learn FastAPI"
    assert data["description"] == "Complete the FastAPI tutorial"
    assert data["status"] == "pending"
    assert data["priority"] == 2

    # Verify auto-generated fields
    assert data["id"] is not None
    assert data["id"] > 0
    assert "created_at" in data
    assert "updated_at" in data


def test_create_task_minimal(client: TestClient):
    """Test creating task with minimal fields (only required title).

    Only 'title' is required. Other fields should use defaults:
    - description: None
    - status: "pending"
    - priority: 1
    """
    response = client.post(
        "/tasks",
        json={"title": "Simple task"}
    )

    assert response.status_code == 201
    data = response.json()

    assert data["title"] == "Simple task"
    assert data["description"] is None
    assert data["status"] == "pending"
    assert data["priority"] == 1


def test_create_task_invalid_status(client: TestClient):
    """Test creating task with invalid status.

    Status must be one of: "pending", "in_progress", "completed"
    Should return 422 Unprocessable Entity
    """
    response = client.post(
        "/tasks",
        json={
            "title": "Task with bad status",
            "status": "invalid_status"  # Not allowed
        }
    )

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_create_task_missing_title(client: TestClient):
    """Test creating task without required title field.

    Title is required and cannot be empty.
    Should return 422 Unprocessable Entity
    """
    response = client.post(
        "/tasks",
        json={"priority": 1}  # Missing title
    )

    assert response.status_code == 422


def test_create_task_invalid_priority(client: TestClient):
    """Test creating task with invalid priority.

    Priority must be 1, 2, or 3
    Should return 422 for values outside this range
    """
    response = client.post(
        "/tasks",
        json={
            "title": "Task",
            "priority": 5  # Invalid
        }
    )

    assert response.status_code == 422

    # Try priority 0
    response = client.post(
        "/tasks",
        json={
            "title": "Task",
            "priority": 0  # Invalid
        }
    )

    assert response.status_code == 422


# ============================================================================
# READ TESTS - GET /tasks
# ============================================================================

def test_list_tasks_empty(client: TestClient):
    """Test listing tasks when database is empty.

    Should return empty list with 200 OK status.
    """
    response = client.get("/tasks")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_tasks_with_data(client: TestClient):
    """Test listing tasks when database has tasks.

    1. Create multiple tasks
    2. List all tasks
    3. Verify all tasks returned
    """
    # Create 3 tasks
    for i in range(3):
        client.post(
            "/tasks",
            json={
                "title": f"Task {i+1}",
                "priority": i + 1
            }
        )

    # List tasks
    response = client.get("/tasks")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["title"] == "Task 1"
    assert data[1]["title"] == "Task 2"
    assert data[2]["title"] == "Task 3"


def test_list_tasks_pagination(client: TestClient):
    """Test pagination with skip and limit parameters.

    Create 5 tasks, request with skip=2 and limit=2
    Should return tasks 3 and 4
    """
    # Create 5 tasks
    for i in range(5):
        client.post(
            "/tasks",
            json={"title": f"Task {i+1}"}
        )

    # Get tasks 3 and 4 (skip 2, limit 2)
    response = client.get("/tasks?skip=2&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Task 3"
    assert data[1]["title"] == "Task 4"


def test_list_tasks_filter_by_status(client: TestClient):
    """Test filtering tasks by status.

    Create tasks with different statuses, then filter by one status
    """
    # Create tasks with different statuses
    client.post("/tasks", json={"title": "Pending 1", "status": "pending"})
    client.post("/tasks", json={"title": "In Progress", "status": "in_progress"})
    client.post("/tasks", json={"title": "Pending 2", "status": "pending"})
    client.post("/tasks", json={"title": "Completed", "status": "completed"})

    # Filter by pending
    response = client.get("/tasks?status_filter=pending")
    data = response.json()
    assert len(data) == 2
    assert all(task["status"] == "pending" for task in data)

    # Filter by completed
    response = client.get("/tasks?status_filter=completed")
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Completed"


# ============================================================================
# READ TESTS - GET /tasks/{task_id}
# ============================================================================

def test_read_task(client: TestClient):
    """Test retrieving a specific task by ID.

    1. Create a task
    2. Retrieve it by ID
    3. Verify all fields match
    """
    # Create task
    create_response = client.post(
        "/tasks",
        json={
            "title": "Test Task",
            "description": "Test Description",
            "priority": 3
        }
    )

    task_id = create_response.json()["id"]

    # Retrieve it
    read_response = client.get(f"/tasks/{task_id}")

    assert read_response.status_code == 200
    data = read_response.json()
    assert data["id"] == task_id
    assert data["title"] == "Test Task"
    assert data["description"] == "Test Description"
    assert data["priority"] == 3


def test_read_task_not_found(client: TestClient):
    """Test retrieving non-existent task.

    Should return 404 Not Found
    """
    response = client.get("/tasks/999")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


# ============================================================================
# UPDATE TESTS - PUT /tasks/{task_id}
# ============================================================================

def test_update_task_all_fields(client: TestClient):
    """Test updating all fields of a task.

    1. Create task with initial values
    2. Update all fields
    3. Verify all changes persisted
    """
    # Create
    create_response = client.post(
        "/tasks",
        json={
            "title": "Original",
            "status": "pending",
            "priority": 1
        }
    )
    task_id = create_response.json()["id"]

    # Update all fields
    update_response = client.put(
        f"/tasks/{task_id}",
        json={
            "title": "Updated",
            "description": "New description",
            "status": "in_progress",
            "priority": 3
        }
    )

    assert update_response.status_code == 200
    data = update_response.json()
    assert data["title"] == "Updated"
    assert data["description"] == "New description"
    assert data["status"] == "in_progress"
    assert data["priority"] == 3
    assert data["id"] == task_id  # ID unchanged


def test_update_task_partial(client: TestClient):
    """Test partial update (only some fields).

    1. Create task
    2. Update only status
    3. Verify other fields unchanged
    """
    # Create
    create_response = client.post(
        "/tasks",
        json={
            "title": "Original Title",
            "description": "Original Description",
            "priority": 1
        }
    )
    task_id = create_response.json()["id"]

    # Update only status
    update_response = client.put(
        f"/tasks/{task_id}",
        json={"status": "completed"}
    )

    assert update_response.status_code == 200
    data = update_response.json()

    # Changed field
    assert data["status"] == "completed"

    # Unchanged fields
    assert data["title"] == "Original Title"
    assert data["description"] == "Original Description"
    assert data["priority"] == 1


def test_update_task_not_found(client: TestClient):
    """Test updating non-existent task.

    Should return 404 Not Found
    """
    response = client.put(
        "/tasks/999",
        json={"status": "completed"}
    )

    assert response.status_code == 404


def test_update_task_invalid_data(client: TestClient):
    """Test updating with invalid data.

    Should return 422 for invalid field values
    """
    # Create
    create_response = client.post(
        "/tasks",
        json={"title": "Task"}
    )
    task_id = create_response.json()["id"]

    # Try to update with invalid status
    update_response = client.put(
        f"/tasks/{task_id}",
        json={"status": "invalid"}
    )

    assert update_response.status_code == 422


# ============================================================================
# DELETE TESTS - DELETE /tasks/{task_id}
# ============================================================================

def test_delete_task(client: TestClient):
    """Test deleting a task.

    1. Create task
    2. Delete it
    3. Verify it's gone (404 on subsequent GET)
    """
    # Create
    create_response = client.post(
        "/tasks",
        json={"title": "To Delete"}
    )
    task_id = create_response.json()["id"]

    # Delete
    delete_response = client.delete(f"/tasks/{task_id}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""  # Empty body for 204

    # Verify it's gone
    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 404


def test_delete_task_not_found(client: TestClient):
    """Test deleting non-existent task.

    Should return 404 Not Found
    """
    response = client.delete("/tasks/999")

    assert response.status_code == 404


def test_delete_does_not_affect_others(client: TestClient):
    """Test that deleting one task doesn't affect others.

    1. Create 3 tasks
    2. Delete task 2
    3. Verify tasks 1 and 3 still exist
    """
    # Create 3 tasks
    task_ids = []
    for i in range(3):
        response = client.post(
            "/tasks",
            json={"title": f"Task {i+1}"}
        )
        task_ids.append(response.json()["id"])

    # Delete middle task
    client.delete(f"/tasks/{task_ids[1]}")

    # Verify first task still exists
    response = client.get(f"/tasks/{task_ids[0]}")
    assert response.status_code == 200

    # Verify middle task is gone
    response = client.get(f"/tasks/{task_ids[1]}")
    assert response.status_code == 404

    # Verify last task still exists
    response = client.get(f"/tasks/{task_ids[2]}")
    assert response.status_code == 200


# ============================================================================
# STATS ENDPOINT TESTS
# ============================================================================

def test_stats_empty(client: TestClient):
    """Test stats when database is empty.

    Should return zero counts for all statuses
    """
    response = client.get("/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["pending"] == 0
    assert data["in_progress"] == 0
    assert data["completed"] == 0


def test_stats_with_data(client: TestClient):
    """Test stats with various tasks.

    Create 5 tasks with different statuses and verify counts
    """
    # Create tasks with different statuses
    client.post("/tasks", json={"title": "P1", "status": "pending"})
    client.post("/tasks", json={"title": "P2", "status": "pending"})
    client.post("/tasks", json={"title": "IP1", "status": "in_progress"})
    client.post("/tasks", json={"title": "C1", "status": "completed"})
    client.post("/tasks", json={"title": "C2", "status": "completed"})

    response = client.get("/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["pending"] == 2
    assert data["in_progress"] == 1
    assert data["completed"] == 2


# ============================================================================
# INTEGRATION TESTS - Multi-step workflows
# ============================================================================

def test_complete_workflow(client: TestClient):
    """Test complete workflow: Create, Read, Update, Delete.

    This integration test simulates a real user flow:
    1. Create a task
    2. Read it back
    3. Update its status
    4. Delete it
    """
    # Step 1: Create
    create_response = client.post(
        "/tasks",
        json={
            "title": "Integration Test Task",
            "description": "Testing complete workflow",
            "status": "pending",
            "priority": 2
        }
    )
    assert create_response.status_code == 201
    task = create_response.json()
    task_id = task["id"]

    # Step 2: Read
    read_response = client.get(f"/tasks/{task_id}")
    assert read_response.status_code == 200
    assert read_response.json()["title"] == "Integration Test Task"

    # Step 3: Update
    update_response = client.put(
        f"/tasks/{task_id}",
        json={"status": "in_progress"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "in_progress"

    # Step 4: Delete
    delete_response = client.delete(f"/tasks/{task_id}")
    assert delete_response.status_code == 204

    # Verify deleted
    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 404


def test_multiple_tasks_independence(client: TestClient):
    """Test that multiple tasks operate independently.

    Ensure operations on one task don't affect others
    """
    # Create 3 independent tasks
    response1 = client.post("/tasks", json={"title": "Task 1", "priority": 1})
    response2 = client.post("/tasks", json={"title": "Task 2", "priority": 2})
    response3 = client.post("/tasks", json={"title": "Task 3", "priority": 3})

    task1_id = response1.json()["id"]
    task2_id = response2.json()["id"]
    task3_id = response3.json()["id"]

    # Update only task 2
    client.put(f"/tasks/{task2_id}", json={"status": "completed"})

    # Verify task 1 unchanged
    task1 = client.get(f"/tasks/{task1_id}").json()
    assert task1["status"] == "pending"

    # Verify task 2 changed
    task2 = client.get(f"/tasks/{task2_id}").json()
    assert task2["status"] == "completed"

    # Verify task 3 unchanged
    task3 = client.get(f"/tasks/{task3_id}").json()
    assert task3["status"] == "pending"
