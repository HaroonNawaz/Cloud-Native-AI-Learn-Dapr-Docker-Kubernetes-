
from fastapi import FastAPI

app = FastAPI()
@app.get("/todos")
def todo_app() -> list[dict[str, int | str]]:
    """Returns a list of todo items."""
    return [{"id": 1, "task": "Buy groceries"},
        {"id": 2, "task": "Walk the dog"},
        {"id": 3, "task": "Read a book"},
         {"id": 4, "task": "Write code"}]

@app.get("/tasks/{task_id}")
def tasks_2(task_id: int) -> dict[str, int | str]:
    """Returns a second list of todo items."""
    if task_id <1:
        return {"error": ""}
    return {"id": task_id, "task": "Go jogging"}



