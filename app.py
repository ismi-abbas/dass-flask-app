# app.py
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# DASS-21 Questions
DASS_QUESTIONS = [
    {"id": 1, "text": "I found it hard to wind down", "category": "stress"},
    {"id": 2, "text": "I was aware of dryness of my mouth", "category": "anxiety"},
    {
        "id": 3,
        "text": "I couldn't seem to experience any positive feeling at all",
        "category": "depression",
    },
    {"id": 4, "text": "I experienced breathing difficulty", "category": "anxiety"},
    {
        "id": 5,
        "text": "I found it hard to work up the initiative to do things",
        "category": "depression",
    },
]


@app.route("/")
def index():
    return render_template("index.html", questions=DASS_QUESTIONS)


@app.route("/submit", methods=["POST"])
def submit_test():
    answers = request.json.get("answers", [])

    # Score calculation logic
    scores = {
        "depression": calculate_category_score(answers, "depression"),
        "anxiety": calculate_category_score(answers, "anxiety"),
        "stress": calculate_category_score(answers, "stress"),
    }

    return jsonify({"scores": scores, "interpretation": interpret_scores(scores)})


def calculate_category_score(answers, category):
    category_questions = [q for q in DASS_QUESTIONS if q["category"] == category]
    return sum(
        answer["score"]
        for answer in answers
        if any(
            q["id"] == answer["questionId"] and q["category"] == category
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
            (11, "Mild"),
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


if __name__ == "__main__":
    app.run(debug=True)
