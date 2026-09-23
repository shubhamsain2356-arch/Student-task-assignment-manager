"""
Student Task & Assignment Manager
----------------------------------
A beginner-friendly full-stack web app built with Flask, vanilla JS,
and JSON files as storage (no database required).

Run with: python app.py
"""

import json
import os
import uuid
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-deploying"  # used to sign session cookies

# ----------------------------------------------------------------------
# File paths for our "database" (plain JSON files)
# ----------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
TASKS_FILE = os.path.join(BASE_DIR, "tasks.json")


# ----------------------------------------------------------------------
# Small helper functions to read/write our JSON "database"
# ----------------------------------------------------------------------
def read_json(path):
    """Read a JSON file and return its contents as a Python list."""
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def write_json(path, data):
    """Write a Python list/dict to a JSON file, nicely formatted."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def find_user_by_email(email):
    users = read_json(USERS_FILE)
    for user in users:
        if user["email"].lower() == email.lower():
            return user
    return None


def get_current_user():
    """Return the logged-in user's dict, or None if nobody is logged in."""
    email = session.get("user_email")
    if not email:
        return None
    return find_user_by_email(email)


# ----------------------------------------------------------------------
# Decorator to protect routes that require login
# ----------------------------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_email" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped_view


# ----------------------------------------------------------------------
# Task helper: compute stats + "overdue" status for the dashboard
# ----------------------------------------------------------------------
def get_user_tasks(email):
    tasks = read_json(TASKS_FILE)
    return [t for t in tasks if t["user_email"].lower() == email.lower()]


def is_overdue(task):
    if task["status"] == "Completed":
        return False
    try:
        due = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
    except (ValueError, KeyError):
        return False
    return due < date.today()


def compute_stats(tasks):
    total = len(tasks)
    completed = len([t for t in tasks if t["status"] == "Completed"])
    overdue = len([t for t in tasks if is_overdue(t)])
    pending = total - completed
    percent = round((completed / total) * 100) if total > 0 else 0
    return {
        "total": total,
        "pending": pending,
        "completed": completed,
        "overdue": overdue,
        "percent": percent,
    }


# ========================================================================
# PAGE ROUTES
# ========================================================================

@app.route("/")
def index():
    if "user_email" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # --- Basic validation ---
        if not name or not email or not password:
            flash("All fields are required.")
            return render_template("signup.html")

        if "@" not in email or "." not in email:
            flash("Please enter a valid email address.")
            return render_template("signup.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.")
            return render_template("signup.html")

        if find_user_by_email(email):
            flash("An account with this email already exists.")
            return render_template("signup.html")

        users = read_json(USERS_FILE)
        new_user = {
            "id": str(uuid.uuid4()),
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "created_date": datetime.now().strftime("%Y-%m-%d"),
        }
        users.append(new_user)
        write_json(USERS_FILE, users)

        session["user_email"] = email
        flash(f"Welcome, {name}! Your account has been created.")
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = find_user_by_email(email)

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.")
            return render_template("login.html")

        session["user_email"] = user["email"]
        flash(f"Welcome back, {user['name']}!")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    tasks = get_user_tasks(user["email"])
    stats = compute_stats(tasks)

    # Recent tasks: sorted by created_date, newest first, top 5
    recent = sorted(tasks, key=lambda t: t.get("created_date", ""), reverse=True)[:5]
    for t in recent:
        t["is_overdue"] = is_overdue(t)

    return render_template("dashboard.html", user=user, stats=stats, recent_tasks=recent)


@app.route("/tasks")
@login_required
def tasks_page():
    user = get_current_user()
    return render_template("tasks.html", user=user)


@app.route("/tasks/add")
@login_required
def add_task_page():
    user = get_current_user()
    return render_template("add_task.html", user=user)


@app.route("/tasks/edit/<task_id>")
@login_required
def edit_task_page(task_id):
    user = get_current_user()
    tasks = read_json(TASKS_FILE)
    task = next((t for t in tasks if t["id"] == task_id), None)

    if not task or task["user_email"].lower() != user["email"].lower():
        flash("Task not found.")
        return redirect(url_for("tasks_page"))

    return render_template("edit_task.html", user=user, task=task)


@app.route("/profile")
@login_required
def profile():
    user = get_current_user()
    tasks = get_user_tasks(user["email"])
    stats = compute_stats(tasks)
    return render_template("profile.html", user=user, stats=stats)


# ========================================================================
# JSON API ROUTES (used by JavaScript on the front end)
# ========================================================================

@app.route("/api/tasks", methods=["GET"])
@login_required
def api_get_tasks():
    user = get_current_user()
    tasks = get_user_tasks(user["email"])
    for t in tasks:
        t["is_overdue"] = is_overdue(t)
    return jsonify(tasks)


@app.route("/api/tasks", methods=["POST"])
@login_required
def api_create_task():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    due_date = (data.get("due_date") or "").strip()

    if not title:
        return jsonify({"error": "Title is required."}), 400

    if due_date:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid due date format. Use YYYY-MM-DD."}), 400

    tasks = read_json(TASKS_FILE)
    new_task = {
        "id": str(uuid.uuid4()),
        "user_email": user["email"],
        "title": title,
        "description": (data.get("description") or "").strip(),
        "subject": (data.get("subject") or "General").strip(),
        "due_date": due_date,
        "priority": data.get("priority") if data.get("priority") in ("Low", "Medium", "High") else "Medium",
        "status": "Pending",
        "created_date": datetime.now().strftime("%Y-%m-%d"),
    }
    tasks.append(new_task)
    write_json(TASKS_FILE, tasks)
    return jsonify(new_task), 201


@app.route("/api/tasks/<task_id>", methods=["PUT"])
@login_required
def api_update_task(task_id):
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    tasks = read_json(TASKS_FILE)
    task = next((t for t in tasks if t["id"] == task_id), None)

    if not task:
        return jsonify({"error": "Task not found."}), 404
    if task["user_email"].lower() != user["email"].lower():
        return jsonify({"error": "Unauthorized."}), 403

    title = data.get("title")
    if title is not None:
        title = title.strip()
        if not title:
            return jsonify({"error": "Title cannot be empty."}), 400
        task["title"] = title

    if "description" in data:
        task["description"] = (data.get("description") or "").strip()
    if "subject" in data:
        task["subject"] = (data.get("subject") or "General").strip()
    if "due_date" in data and data.get("due_date"):
        try:
            datetime.strptime(data["due_date"], "%Y-%m-%d")
            task["due_date"] = data["due_date"]
        except ValueError:
            return jsonify({"error": "Invalid due date format. Use YYYY-MM-DD."}), 400
    if "priority" in data and data.get("priority") in ("Low", "Medium", "High"):
        task["priority"] = data["priority"]
    if "status" in data and data.get("status") in ("Pending", "Completed"):
        task["status"] = data["status"]

    write_json(TASKS_FILE, tasks)
    return jsonify(task)


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
@login_required
def api_delete_task(task_id):
    user = get_current_user()
    tasks = read_json(TASKS_FILE)
    task = next((t for t in tasks if t["id"] == task_id), None)

    if not task:
        return jsonify({"error": "Task not found."}), 404
    if task["user_email"].lower() != user["email"].lower():
        return jsonify({"error": "Unauthorized."}), 403

    tasks = [t for t in tasks if t["id"] != task_id]
    write_json(TASKS_FILE, tasks)
    return jsonify({"message": "Task deleted."})


# ========================================================================
# Entry point
# ========================================================================
if __name__ == "__main__":
    # Make sure our "database" files exist before the app starts
    if not os.path.exists(USERS_FILE):
        write_json(USERS_FILE, [])
    if not os.path.exists(TASKS_FILE):
        write_json(TASKS_FILE, [])

    app.run(debug=True)