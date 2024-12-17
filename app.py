from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    session,
)
from database import get_db_connection, init_db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session
from constant import DASS_QUESTIONS
import sqlite3
from datetime import datetime, timedelta
import functools

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

app.secret_key = "NYWFcxLeXCONcvuSJDKdPtnzojIRn8WeZoI2h+VnsKw="


# Decorator for counsellor-only routes
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def counsellor_login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id") or session.get("role") != "counsellor":
            return redirect(url_for("counsellor_login"))
        return f(*args, **kwargs)

    return decorated_function


def dateformat(value, format="%Y-%m-%d"):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    if isinstance(value, datetime):
        return value.strftime(format)

    return value


def get_current_datetime():
    return datetime.now()


app.jinja_env.filters["dateformat"] = dateformat
app.jinja_env.globals["now"] = get_current_datetime
app.jinja_env.globals["timedelta"] = timedelta


@app.route("/")
def index():
    return render_template("index.html", questions=DASS_QUESTIONS)


@app.route("/question/<question_id>")
@login_required
def question(question_id):
    question = next((q for q in DASS_QUESTIONS if q["id"] == int(question_id)), None)
    return render_template(
        "question.html", question=question, DASS_QUESTIONS=DASS_QUESTIONS
    )


@app.route("/results")
@login_required
def results():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    try:
        conn = get_db_connection()
        scores = conn.execute(
            "SELECT depression_score, anxiety_score, stress_score, date_taken, answer FROM dass_score WHERE user_id = ?",
            (session["user_id"],),
        ).fetchone()
        conn.close()
    except sqlite3.IntegrityError:
        scores = None

    if scores:
        return render_template("results.html", scores=scores)
    return render_template("results.html")


@app.route("/submit", methods=["POST"])
@login_required
def submit_test():
    answers = request.json.get("answers", [])

    # Score calculation logic
    scores = {
        "depression": calculate_category_score(answers, "depression"),
        "anxiety": calculate_category_score(answers, "anxiety"),
        "stress": calculate_category_score(answers, "stress"),
    }

    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO dass_score (user_id, depression_score, anxiety_score, stress_score, answer) VALUES (?, ?, ?, ?, ?)",
            (
                session["user_id"],
                scores["depression"],
                scores["anxiety"],
                scores["stress"],
                str(answers),
            ),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        pass

    return jsonify({"scores": scores, "interpretation": interpret_scores(scores)})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        form_data = request.form
        email = form_data.get("email")
        password = form_data.get("password")

        if not email or not password:
            flash("Please fill out all fields", "error")
            return redirect(url_for("login"))

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM students WHERE email = ?", (email,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = "student"

            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/user/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        phone = request.form["phone"]
        age = request.form["age"]
        gender = request.form["gender"]

        if not username or not email or not password:
            flash("Please fill out all fields", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO students (username, email, password, phone, age, gender) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    username,
                    email,
                    hashed_password,
                    phone,
                    age,
                    gender,
                ),
            )
            conn.commit()
            conn.close()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists", "error")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/get_user_info")
@login_required
def get_user_info():
    if not session.get("user_id"):
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_db_connection()
        if session["role"] == "counsellor":
            user = conn.execute(
                "SELECT username, email FROM counsellors WHERE id = ?",
                (session["user_id"],),
            ).fetchone()
        else:
            user = conn.execute(
                "SELECT username, email FROM students WHERE id = ?",
                (session["user_id"],),
            ).fetchone()
        conn.close()

        return jsonify(
            {
                "username": user["username"],
                "email": user["email"],
                "notifications": True,  # Placeholder, add a notifications column to users table
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/update_user_settings", methods=["POST"])
@login_required
def update_user_settings():
    if not session.get("user_id"):
        return jsonify({"success": False, "message": "Not logged in"}), 401

    data = request.get_json()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if session["role"] == "counsellor":
            # Update username and email
            cursor.execute(
                "UPDATE counsellors SET username = ?, email = ? WHERE id = ?",
                (data["username"], data["email"], session["user_id"]),
            )

            # Update password if provided
            if "password" in data and data["password"]:
                hashed_password = generate_password_hash(data["password"])
                cursor.execute(
                    "UPDATE counsellors SET password = ? WHERE id = ?",
                    (hashed_password, session["user_id"]),
                )

            conn.commit()
            conn.close()

            return jsonify({"success": True})

        # Update username and email
        cursor.execute(
            "UPDATE students SET username = ?, email = ? WHERE id = ?",
            (data["username"], data["email"], session["user_id"]),
        )

        # Update password if provided
        if "password" in data and data["password"]:
            hashed_password = generate_password_hash(data["password"])
            cursor.execute(
                "UPDATE students SET password = ? WHERE id = ?",
                (hashed_password, session["user_id"]),
            )

        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    if not session.get("user_id"):
        return jsonify({"success": False, "message": "Not logged in"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete user and associated data
        cursor.execute(
            "DELETE FROM dass_score WHERE user_id = ?", (session["user_id"],)
        )
        cursor.execute("DELETE FROM students WHERE id = ?", (session["user_id"],))

        conn.commit()
        conn.close()

        # Clear session
        session.clear()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/counsellor/stats")
@counsellor_login_required
def counsellor_stats():
    if not session.get("user_id"):
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_db_connection()

        # Total students
        total_students = conn.execute(
            "SELECT COUNT(*) as count FROM students"
        ).fetchone()["count"]

        # Monthly assessments
        monthly_assessments = conn.execute(
            """
            SELECT COUNT(*) as count 
            FROM dass_score 
            WHERE strftime('%Y-%m', date_taken) = strftime('%Y-%m', 'now')
        """
        ).fetchone()["count"]

        # High-risk students (define high-risk as having severe scores in any category)
        high_risk_students = conn.execute(
            """
            SELECT COUNT(DISTINCT user_id) as count 
            FROM dass_score 
            WHERE depression_score > 20 OR anxiety_score > 10 OR stress_score > 16
        """
        ).fetchone()["count"]

        conn.close()

        return jsonify(
            {
                "totalStudents": total_students,
                "monthlyAssessments": monthly_assessments,
                "highRiskStudents": high_risk_students,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/counsellor/recent_assessments")
@counsellor_login_required
def recent_assessments():
    if not session.get("user_id"):
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_db_connection()

        # Fetch recent assessments with student details
        assessments = conn.execute(
            """
            SELECT 
                ds.id, 
                s.username as student_name, 
                ds.date_taken as date, 
                ds.depression_score, 
                ds.anxiety_score, 
                ds.stress_score
            FROM dass_score ds
            JOIN students s ON ds.user_id = s.id
            ORDER BY ds.date_taken DESC
            LIMIT 10
        """
        ).fetchall()

        conn.close()

        # Convert to list of dictionaries
        return jsonify([dict(assessment) for assessment in assessments])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/counsellor/upcoming_appointments")
@counsellor_login_required
def upcoming_appointments():
    if not session.get("user_id"):
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_db_connection()

        # Fetch upcoming appointments with student details
        # Note: You'll need to create an appointments table first
        appointments = conn.execute(
            """
            SELECT 
                a.id, 
                s.username as student_name, 
                a.date, 
                a.time, 
                a.status
            FROM appointments a
            JOIN students s ON a.student_id = s.id
            WHERE a.date >= date('now')
            ORDER BY a.date, a.time
            LIMIT 10
        """
        ).fetchall()

        conn.close()

        # Convert to list of dictionaries
        return jsonify([dict(appointment) for appointment in appointments])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/book_appointment", methods=["GET", "POST"])
@login_required
def book_appointment():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        data = request.get_json()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if the student already has a pending or confirmed appointment
            existing_appointment = cursor.execute(
                "SELECT * FROM appointments WHERE student_id = ? AND status IN ('pending', 'confirmed')",
                (session["user_id"],),
            ).fetchone()

            if existing_appointment:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "You already have a pending or confirmed appointment.",
                        }
                    ),
                    400,
                )

            # Insert new appointment
            cursor.execute(
                """
                INSERT INTO appointments 
                (student_id, date, time, reason, status) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    data.get("date"),
                    data.get("time"),
                    data.get("reason", "General Counselling"),
                    "pending",
                ),
            )

            conn.commit()
            conn.close()

            return jsonify(
                {"success": True, "message": "Appointment booked successfully!"}
            )

        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    # GET request - render booking page
    conn = get_db_connection()
    cursor = conn.cursor()
    cousellors = cursor.execute("SELECT * FROM counsellors")
    return render_template("book_appointment.html", counsellors=cousellors)


def calculate_category_score(answers, category):
    category_questions = [q for q in DASS_QUESTIONS if q["category"] == category]
    return sum(
        answer["answer"] * 2
        for answer in answers
        if any(
            q["id"] == answer["id"] and q["category"] == category
            for q in category_questions
        )
    )


def interpret_scores(scores):
    interpretations = {
        "depression": [
            (0, "Normal"),
            (10, "Mild"),
            (14, "Moderate"),
            (21, "Severe"),
            (float("inf"), "Extremely Severe"),
        ],
        "anxiety": [
            (0, "Normal"),
            (8, "Mild"),
            (10, "Moderate"),
            (15, "Severe"),
            (float("inf"), "Extremely Severe"),
        ],
        "stress": [
            (0, "Normal"),
            (15, "Mild"),
            (19, "Moderate"),
            (26, "Severe"),
            (float("inf"), "Extremely Severe"),
        ],
    }

    result = {}
    for category, score in scores.items():
        for threshold, level in interpretations[category]:
            if score <= threshold:
                result[category] = {"score": score, "level": level}
                break

    return result


@app.route("/counsellor/register", methods=["GET", "POST"])
def counsellor_register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        phone = request.form.get("phone", "")

        # Validation
        if not username or not email or not password:
            flash("All fields are required", "error")
            return redirect(url_for("counsellor_register"))

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(url_for("counsellor_register"))

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if username or email already exists in counsellors
            existing_user = cursor.execute(
                "SELECT * FROM counsellors WHERE username = ? OR email = ?",
                (username, email),
            ).fetchone()

            if existing_user:
                flash("Username or email already exists", "error")
                return redirect(url_for("counsellor_register"))

            # Hash the password
            hashed_password = generate_password_hash(password)

            # Insert new counsellor
            cursor.execute(
                """
                INSERT INTO counsellors 
                (username, email, password, phone) 
                VALUES (?, ?, ?, ?)
                """,
                (username, email, hashed_password, phone),
            )
            conn.commit()
            conn.close()

            flash("Counsellor registration successful", "success")
            return redirect(url_for("login"))

        except Exception as e:
            flash(f"Registration error: {str(e)}", "error")
            return redirect(url_for("counsellor_register"))

    return render_template("counsellor_register.html")


@app.route("/counsellor/appointments")
@counsellor_login_required
def manage_appointments():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Fetch appointments with student details
        appointments = cursor.execute(
            """
            SELECT 
                a.id, 
                s.username as student_name, 
                a.date, 
                a.time, 
                a.reason, 
                a.status,
                a.created_at
            FROM appointments a
            JOIN students s ON a.student_id = s.id
            ORDER BY a.created_at DESC
            """
        ).fetchall()
        conn.close()

        return render_template("manage_appointments.html", appointments=appointments)
    except Exception as e:
        print(e)
        flash(f"Error fetching appointments: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/counsellor/update_appointment/<int:appointment_id>", methods=["POST"])
@counsellor_login_required
def update_appointment(appointment_id):
    status = request.form.get("status")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update appointment status
        cursor.execute(
            "UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id)
        )
        conn.commit()
        conn.close()

        flash("Appointment updated successfully", "success")
        return redirect(url_for("manage_appointments"))
    except Exception as e:
        flash(f"Error updating appointment: {str(e)}", "error")
        return redirect(url_for("manage_appointments"))


@app.route("/counsellor/appointments")
@counsellor_login_required
def counsellor_appointments():
    try:
        conn = get_db_connection()
        appointments = conn.execute(
            """
            SELECT 
                a.id, 
                s.username as student_name, 
                a.date, 
                a.time, 
                a.reason, 
                a.status
            FROM appointments a
            JOIN students s ON a.student_id = s.id
            ORDER BY a.date, a.time
            """
        ).fetchall()
        conn.close()

        return render_template("manage_appointments.html", appointments=appointments)
    except Exception as e:
        flash(f"Error fetching appointments: {str(e)}", "error")
        return redirect(url_for("counsellor_dashboard"))


@app.route("/counsellor/update_appointment/<int:appointment_id>", methods=["POST"])
@counsellor_login_required
def counsellor_update_appointment(appointment_id):
    status = request.form.get("status")

    try:
        conn = get_db_connection()
        conn.execute(
            "UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id)
        )
        conn.commit()
        conn.close()

        flash("Appointment updated successfully", "success")
        return redirect(url_for("counsellor_appointments"))
    except Exception as e:
        flash(f"Error updating appointment: {str(e)}", "error")
        return redirect(url_for("counsellor_appointments"))


@app.route("/counsellor/login", methods=["GET", "POST"])
def counsellor_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if counsellor exists
            counsellor = cursor.execute(
                "SELECT * FROM counsellors WHERE email = ?", (email,)
            ).fetchone()
            conn.close()

            if counsellor and check_password_hash(counsellor["password"], password):
                # Set session for counsellor
                session["user_id"] = counsellor["id"]
                session["username"] = counsellor["username"]
                session["role"] = "counsellor"

                flash("Counsellor login successful!", "success")
                return redirect(url_for("counsellor_dashboard"))
            else:
                flash("Invalid email or password", "error")
                return redirect(url_for("counsellor_login"))

        except Exception as e:
            flash(f"Login error: {str(e)}", "error")
            return redirect(url_for("counsellor_login"))

    return render_template("counsellor_login.html")


@app.route("/counsellor/dashboard")
# @counsellor_login_required
def counsellor_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch dashboard statistics
        total_students = cursor.execute(
            "SELECT COUNT(*) as count FROM students"
        ).fetchone()["count"]

        monthly_assessments = cursor.execute(
            """
            SELECT COUNT(*) as count 
            FROM dass_score 
            WHERE date_taken >= date('now', '-1 month')
            """
        ).fetchone()["count"]

        high_risk_students = cursor.execute(
            """
            SELECT COUNT(*) as count 
            FROM dass_score 
            WHERE depression_score > 20 * 2 OR anxiety_score > 14 * 2 OR stress_score > 25 * 2
            """
        ).fetchone()["count"]

        conn.close()

        return render_template(
            "counsellor_dashboard.html",
            total_students=total_students,
            monthly_assessments=monthly_assessments,
            high_risk_students=high_risk_students,
        )
    except Exception as e:
        flash(f"Dashboard error: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/assessments")
@counsellor_login_required
def assessments():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all all_assessments for the current user, ordered by date descending
        cursor.execute("""
            SELECT ds.id, user_id, depression_score, anxiety_score, stress_score, date_taken, s.username
            FROM dass_score ds
            JOIN students s ON ds.user_id = s.id
            ORDER BY date_taken DESC
        """)

        all_assessments = cursor.fetchall()
        cursor.close()
        conn.close()

        return render_template("assessment.html", all_assessments=all_assessments)

    except Exception as e:
        print({str(e)})
        flash(f"Error retrieving assessment history: {str(e)}", "error")
        return redirect(url_for("counsellor_dashboard"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
