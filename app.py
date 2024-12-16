from re import S
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
from datetime import datetime

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

app.secret_key = "NYWFcxLeXCONcvuSJDKdPtnzojIRn8WeZoI2h+VnsKw="


def dateformat(value, format="%Y-%m-%d"):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    if isinstance(value, datetime):
        return value.strftime(format)

    return value


app.jinja_env.filters["dateformat"] = dateformat


@app.route("/")
def index():
    return render_template("index.html", questions=DASS_QUESTIONS)


@app.route("/question/<question_id>")
def question(question_id):
    question = next((q for q in DASS_QUESTIONS if q["id"] == int(question_id)), None)
    return render_template(
        "question.html", question=question, DASS_QUESTIONS=DASS_QUESTIONS
    )


@app.route("/results")
def results():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    try:
        conn = get_db_connection()
        scores = conn.execute(
            "SELECT depression_score, anxiety_score, stress_score, date_taken FROM dass_score WHERE user_id = ?",
            (session["user_id"],),
        ).fetchone()
        conn.close()
    except sqlite3.IntegrityError:
        scores = None

    if scores:
        return render_template("results.html", scores=scores)
    return render_template("results.html")


@app.route("/submit", methods=["POST"])
def submit_test():
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401

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
            "INSERT INTO dass_score (user_id, depression_score, anxiety_score, stress_score) VALUES (?, ?, ?, ?)",
            (
                session["user_id"],
                scores["depression"],
                scores["anxiety"],
                scores["stress"],
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

            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")


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


def calculate_category_score(answers, category):
    category_questions = [q for q in DASS_QUESTIONS if q["category"] == category]
    return sum(
        answer["answer"]
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


init_db()

if __name__ == "__main__":
    app.run(debug=True)
