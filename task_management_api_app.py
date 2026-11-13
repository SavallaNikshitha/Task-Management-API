"""
Task Management API
-------------------
A professional Flask + SQLite REST API for managing tasks.

Install:
    pip install Flask

Run:
    python app.py

API:
    GET    /api/tasks
    POST   /api/tasks
    GET    /api/tasks/<id>
    PUT    /api/tasks/<id>
    PATCH  /api/tasks/<id>/status
    DELETE /api/tasks/<id>
    GET    /health

Example POST body:
{
  "title": "Prepare project presentation",
  "description": "Complete the architecture slides",
  "priority": "high",
  "status": "pending",
  "due_date": "2026-11-20"
}
"""

from flask import Flask, request, jsonify
import sqlite3
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
DATABASE = Path(__file__).with_name("tasks.db")

VALID_STATUSES = {"pending", "in_progress", "completed"}
VALID_PRIORITIES = {"low", "medium", "high"}


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'pending',
                due_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def task_to_dict(row):
    return dict(row) if row else None


def error(message, status_code=400):
    return jsonify({"success": False, "message": message}), status_code


@app.get("/")
def home():
    return jsonify({
        "service": "Task Management API",
        "version": "1.0.0",
        "documentation": {
            "GET /api/tasks": "List tasks. Optional filters: status, priority",
            "POST /api/tasks": "Create a task",
            "GET /api/tasks/<id>": "Get one task",
            "PUT /api/tasks/<id>": "Update a task",
            "PATCH /api/tasks/<id>/status": "Update task status",
            "DELETE /api/tasks/<id>": "Delete a task"
        }
    })


@app.get("/health")
def health():
    return jsonify({"success": True, "status": "healthy"})


@app.get("/api/tasks")
def list_tasks():
    status = request.args.get("status")
    priority = request.args.get("priority")

    query = "SELECT * FROM tasks WHERE 1=1"
    values = []

    if status:
        if status not in VALID_STATUSES:
            return error("Invalid status filter.")
        query += " AND status = ?"
        values.append(status)

    if priority:
        if priority not in VALID_PRIORITIES:
            return error("Invalid priority filter.")
        query += " AND priority = ?"
        values.append(priority)

    query += " ORDER BY created_at DESC"

    with get_db() as db:
        rows = db.execute(query, values).fetchall()

    return jsonify({
        "success": True,
        "count": len(rows),
        "tasks": [task_to_dict(row) for row in rows]
    })


@app.post("/api/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()

    if not title:
        return error("The title field is required.")

    priority = data.get("priority", "medium")
    status = data.get("status", "pending")

    if priority not in VALID_PRIORITIES:
        return error("Priority must be low, medium, or high.")

    if status not in VALID_STATUSES:
        return error("Status must be pending, in_progress, or completed.")

    due_date = data.get("due_date")
    if due_date:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            return error("due_date must use YYYY-MM-DD format.")

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO tasks
            (title, description, priority, status, due_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            str(data.get("description", "")).strip(),
            priority,
            status,
            due_date,
            now,
            now
        ))
        task_id = cursor.lastrowid
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    return jsonify({"success": True, "message": "Task created.", "task": task_to_dict(row)}), 201


@app.get("/api/tasks/<int:task_id>")
def get_task(task_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    if not row:
        return error("Task not found.", 404)

    return jsonify({"success": True, "task": task_to_dict(row)})


@app.put("/api/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True) or {}

    with get_db() as db:
        existing = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not existing:
            return error("Task not found.", 404)

        title = str(data.get("title", existing["title"])).strip()
        description = str(data.get("description", existing["description"])).strip()
        priority = data.get("priority", existing["priority"])
        status = data.get("status", existing["status"])
        due_date = data.get("due_date", existing["due_date"])

        if not title:
            return error("The title cannot be empty.")
        if priority not in VALID_PRIORITIES:
            return error("Priority must be low, medium, or high.")
        if status not in VALID_STATUSES:
            return error("Invalid status.")
        if due_date:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                return error("due_date must use YYYY-MM-DD format.")

        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        db.execute("""
            UPDATE tasks
            SET title=?, description=?, priority=?, status=?, due_date=?, updated_at=?
            WHERE id=?
        """, (title, description, priority, status, due_date, now, task_id))
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    return jsonify({"success": True, "message": "Task updated.", "task": task_to_dict(row)})


@app.patch("/api/tasks/<int:task_id>/status")
def update_status(task_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")

    if status not in VALID_STATUSES:
        return error("Status must be pending, in_progress, or completed.")

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with get_db() as db:
        cursor = db.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
            (status, now, task_id)
        )
        if cursor.rowcount == 0:
            return error("Task not found.", 404)
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

    return jsonify({"success": True, "message": "Task status updated.", "task": task_to_dict(row)})


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    with get_db() as db:
        cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    if cursor.rowcount == 0:
        return error("Task not found.", 404)

    return jsonify({"success": True, "message": "Task deleted."})


initialize_database()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
