from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "student_project_management_key"

DATABASE = "database.db"


# Connect to the database
def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# Create database tables
def initialize_database():
    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            start_date TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'Planning'
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            assigned_to TEXT,
            start_date TEXT,
            deadline TEXT,
            estimated_hours REAL DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            probability INTEGER NOT NULL,
            impact INTEGER NOT NULL,
            mitigation TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    connection.commit()
    connection.close()


# Dashboard
@app.route("/")
def index():
    connection = get_db_connection()

    total_projects = connection.execute(
        "SELECT COUNT(*) FROM projects"
    ).fetchone()[0]

    total_tasks = connection.execute(
        "SELECT COUNT(*) FROM tasks"
    ).fetchone()[0]

    completed_tasks = connection.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'Completed'"
    ).fetchone()[0]

    overdue_tasks = connection.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE deadline < ?
        AND deadline != ''
        AND status != 'Completed'
    """, (date.today().isoformat(),)).fetchone()[0]

    connection.close()

    return render_template(
        "index.html",
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks
    )


# View and create projects
@app.route("/projects", methods=["GET", "POST"])
def projects():
    connection = get_db_connection()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        start_date = request.form.get("start_date", "")
        deadline = request.form.get("deadline", "")

        if not name:
            connection.close()
            flash("Project name is required.")
            return redirect(url_for("projects"))

        if start_date and deadline and start_date > deadline:
            connection.close()
            flash("Project deadline cannot be before its start date.")
            return redirect(url_for("projects"))

        connection.execute("""
            INSERT INTO projects
            (name, description, start_date, deadline)
            VALUES (?, ?, ?, ?)
        """, (name, description, start_date, deadline))

        connection.commit()
        connection.close()

        flash("Project created successfully!")
        return redirect(url_for("projects"))

    all_projects = connection.execute(
        "SELECT * FROM projects ORDER BY id DESC"
    ).fetchall()

    connection.close()

    return render_template("projects.html", projects=all_projects)


# View and create tasks
@app.route("/tasks", methods=["GET", "POST"])
def tasks():
    connection = get_db_connection()

    if request.method == "POST":
        project_id = request.form.get("project_id")
        title = request.form.get("title", "").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        start_date = request.form.get("start_date", "")
        deadline = request.form.get("deadline", "")
        estimated_hours = request.form.get("estimated_hours", "0")

        valid_project = connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()

        if not valid_project or not title:
            connection.close()
            flash("Select a valid project and enter a task title.")
            return redirect(url_for("tasks"))

        if start_date and deadline and start_date > deadline:
            connection.close()
            flash("Task deadline cannot be before its start date.")
            return redirect(url_for("tasks"))

        try:
            estimated_hours = float(estimated_hours)

            if estimated_hours < 0:
                raise ValueError

        except ValueError:
            connection.close()
            flash("Estimated hours must be a non-negative number.")
            return redirect(url_for("tasks"))

        connection.execute("""
            INSERT INTO tasks
            (project_id, title, assigned_to, start_date,
             deadline, estimated_hours)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            title,
            assigned_to,
            start_date,
            deadline,
            estimated_hours
        ))

        connection.commit()
        connection.close()

        flash("Task added successfully!")
        return redirect(url_for("tasks"))

    all_tasks = connection.execute("""
        SELECT tasks.*, projects.name AS project_name
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        ORDER BY tasks.id DESC
    """).fetchall()

    all_projects = connection.execute(
        "SELECT * FROM projects ORDER BY name"
    ).fetchall()

    connection.close()

    return render_template(
        "tasks.html",
        tasks=all_tasks,
        projects=all_projects,
        today=date.today().isoformat()
    )


# Delete a task
@app.route("/delete_task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    connection = get_db_connection()

    task = connection.execute(
        "SELECT id FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if task is None:
        connection.close()
        flash("Task not found. It may already have been deleted.")
        return redirect(url_for("tasks"))

    connection.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    connection.commit()
    connection.close()

    flash("Task deleted successfully!")
    return redirect(url_for("tasks"))


# View and create project risks
@app.route("/risks", methods=["GET", "POST"])
def risks():
    connection = get_db_connection()

    if request.method == "POST":
        project_id = request.form.get("project_id")
        description = request.form.get("description", "").strip()
        mitigation = request.form.get("mitigation", "").strip()

        try:
            probability = int(request.form.get("probability", ""))
            impact = int(request.form.get("impact", ""))

            if probability not in range(1, 6) or impact not in range(1, 6):
                raise ValueError

        except ValueError:
            connection.close()
            flash("Probability and impact must be between 1 and 5.")
            return redirect(url_for("risks"))

        valid_project = connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()

        if not valid_project or not description:
            connection.close()
            flash("Select a project and enter a risk description.")
            return redirect(url_for("risks"))

        connection.execute("""
            INSERT INTO risks
            (project_id, description, probability, impact, mitigation)
            VALUES (?, ?, ?, ?, ?)
        """, (
            project_id,
            description,
            probability,
            impact,
            mitigation
        ))

        connection.commit()
        connection.close()

        flash("Risk recorded successfully!")
        return redirect(url_for("risks"))

    all_risks = connection.execute("""
        SELECT risks.*, projects.name AS project_name,
               (risks.probability * risks.impact) AS risk_score
        FROM risks
        JOIN projects ON risks.project_id = projects.id
        ORDER BY risk_score DESC
    """).fetchall()

    all_projects = connection.execute(
        "SELECT * FROM projects ORDER BY name"
    ).fetchall()

    connection.close()

    return render_template(
        "risks.html",
        risks=all_risks,
        projects=all_projects
    )


# Gantt Chart
@app.route("/gantt")
def gantt():
    connection = get_db_connection()

    all_projects = connection.execute("""
        SELECT id, name
        FROM projects
        ORDER BY name
    """).fetchall()

    selected_project = request.args.get("project_id", "").strip()

    # Validate the project filter
    if selected_project:
        try:
            selected_project_id = int(selected_project)

            valid_project = connection.execute(
                "SELECT id FROM projects WHERE id = ?",
                (selected_project_id,)
            ).fetchone()

            if not valid_project:
                selected_project = ""
        except ValueError:
            selected_project = ""

    # Retrieve tasks for the selected project or all projects
    if selected_project:
        all_tasks = connection.execute("""
            SELECT tasks.*, projects.name AS project_name
            FROM tasks
            JOIN projects ON tasks.project_id = projects.id
            WHERE tasks.project_id = ?
            ORDER BY tasks.start_date, tasks.deadline, tasks.id
        """, (int(selected_project),)).fetchall()
    else:
        all_tasks = connection.execute("""
            SELECT tasks.*, projects.name AS project_name
            FROM tasks
            JOIN projects ON tasks.project_id = projects.id
            ORDER BY tasks.start_date, tasks.deadline, tasks.id
        """).fetchall()

    connection.close()

    scheduled_tasks = []
    unscheduled_tasks = []

    # Convert date strings into real calendar dates
    for row in all_tasks:
        task = dict(row)

        try:
            start = date.fromisoformat(task["start_date"])
            end = date.fromisoformat(task["deadline"])

            if end < start:
                raise ValueError

            task["start_date"] = start.isoformat()
            task["deadline"] = end.isoformat()

            scheduled_tasks.append(task)

        except (ValueError, TypeError):
            unscheduled_tasks.append(task)

    # Calculate timeline positions using actual calendar days
    if scheduled_tasks:
        timeline_start = min(
            date.fromisoformat(task["start_date"])
            for task in scheduled_tasks
        )

        timeline_end = max(
            date.fromisoformat(task["deadline"])
            for task in scheduled_tasks
        )

        # Add one day so a single-day task has a visible width
        total_days = (timeline_end - timeline_start).days + 1

        for task in scheduled_tasks:
            start = date.fromisoformat(task["start_date"])
            end = date.fromisoformat(task["deadline"])

            offset_days = (start - timeline_start).days
            duration_days = (end - start).days + 1

            task["left_percent"] = (
                offset_days / total_days
            ) * 100

            task["width_percent"] = (
                duration_days / total_days
            ) * 100

            task["duration_days"] = duration_days

    else:
        timeline_start = None
        timeline_end = None
        total_days = 0

    return render_template(
        "gantt.html",
        projects=all_projects,
        tasks=scheduled_tasks,
        unscheduled_tasks=unscheduled_tasks,
        selected_project=selected_project,
        timeline_start=timeline_start,
        timeline_end=timeline_end,
        total_days=total_days,
        today=date.today().isoformat()
    )


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
