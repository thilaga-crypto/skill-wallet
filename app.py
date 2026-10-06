import json
import os
import random
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fitbuddy-dev-secret-change-me")
app.config["DATABASE"] = str(BASE_DIR / "fitbuddy.db")

PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
OFFLINE_FALLBACK = os.getenv("OFFLINE_FALLBACK", "true").lower() == "true"


GOALS = [
    "General wellness",
    "Weight loss",
    "Muscle gain",
    "Improve stamina",
    "Improve flexibility",
]

INTENSITIES = ["Low", "Medium", "High"]


def get_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workout_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                weight REAL NOT NULL,
                goal TEXT NOT NULL,
                intensity TEXT NOT NULL,
                source TEXT NOT NULL,
                model_used TEXT,
                created_at TEXT NOT NULL,
                plan_json TEXT NOT NULL
            )
            """
        )


def validate_form(form):
    errors = []
    user_id = form.get("user_id", "").strip()
    name = form.get("name", "").strip()
    goal = form.get("goal", "").strip()
    intensity = form.get("intensity", "").strip()

    try:
        age = int(form.get("age", ""))
    except ValueError:
        age = 0

    try:
        weight = float(form.get("weight", ""))
    except ValueError:
        weight = 0

    if not user_id:
        errors.append("User ID is required.")
    if not name:
        errors.append("Name is required.")
    if age < 13 or age > 100:
        errors.append("Age must be between 13 and 100.")
    if weight < 25 or weight > 300:
        errors.append("Weight must be between 25 kg and 300 kg.")
    if goal not in GOALS:
        errors.append("Please select a valid fitness goal.")
    if intensity not in INTENSITIES:
        errors.append("Please select a valid intensity.")

    data = {
        "user_id": user_id,
        "name": name,
        "age": age,
        "weight": weight,
        "goal": goal,
        "intensity": intensity,
    }
    return data, errors


def build_prompt(data):
    return f"""
You are FitBuddy, a wellness-oriented fitness planner.

Create a practical, beginner-friendly 7-day activity and recovery plan for this user:
- Name: {data['name']}
- Age: {data['age']}
- Weight: {data['weight']} kg
- Fitness goal: {data['goal']}
- Preferred intensity: {data['intensity']}

Important rules:
1. This is general wellness guidance, not medical advice.
2. Do not diagnose, treat, or make medical claims.
3. Keep the plan realistic and safe for a generally healthy adult.
4. Include at least one lighter recovery day.
5. Each day should contain a warm-up, main workout, cool-down, and recovery note.
6. Avoid extreme exercise volume.
7. Use simple exercises that can be done at home or in a basic gym.

Return ONLY valid JSON using exactly this structure:
{{
  "summary": "short overview",
  "days": [
    {{
      "day": "Day 1",
      "focus": "focus name",
      "duration": "example: 35-45 minutes",
      "warmup": ["item 1", "item 2"],
      "workout": [
        {{
          "exercise": "exercise name",
          "sets": "example: 3",
          "reps": "example: 10-12"
        }}
      ],
      "cooldown": ["item 1", "item 2"],
      "recovery": "short recovery guidance"
    }}
  ],
  "safety_note": "short safety note"
}}

The "days" array must contain exactly 7 days.
""".strip()


def is_retryable_error(exc):
    text = str(exc).lower()
    retry_markers = [
        "503",
        "unavailable",
        "high demand",
        "overloaded",
        "429",
        "resource_exhausted",
        "rate limit",
    ]
    return any(marker in text for marker in retry_markers)


def normalize_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("AI response was not a JSON object.")

    days = plan.get("days")
    if not isinstance(days, list) or len(days) != 7:
        raise ValueError("AI response did not contain exactly 7 days.")

    for index, day in enumerate(days, start=1):
        if not isinstance(day, dict):
            raise ValueError("Invalid day format.")
        day.setdefault("day", f"Day {index}")
        day.setdefault("focus", "Balanced activity")
        day.setdefault("duration", "30-40 minutes")
        day.setdefault("warmup", ["Easy marching - 3 minutes"])
        day.setdefault("workout", [])
        day.setdefault("cooldown", ["Gentle stretching - 5 minutes"])
        day.setdefault("recovery", "Hydrate and get adequate sleep.")

    plan.setdefault("summary", "A balanced 7-day activity and recovery plan.")
    plan.setdefault(
        "safety_note",
        "Stop activity if you feel unwell, dizzy, or have unusual pain and seek qualified medical help.",
    )
    return plan


def call_gemini(data):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "PASTE_YOUR_GEMINI_API_KEY_HERE":
        raise RuntimeError(
            "Gemini API key is missing. Open the .env file and set GEMINI_API_KEY."
        )

    client = genai.Client(api_key=api_key)
    prompt = build_prompt(data)

    models = []
    for model in [PRIMARY_MODEL, FALLBACK_MODEL]:
        if model and model not in models:
            models.append(model)

    last_error = None

    for model_name in models:
        for attempt in range(MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.6,
                        response_mime_type="application/json",
                    ),
                )

                if not response.text:
                    raise RuntimeError("Gemini returned an empty response.")

                plan = json.loads(response.text)
                return normalize_plan(plan), model_name

            except Exception as exc:
                last_error = exc

                if not is_retryable_error(exc):
                    raise

                if attempt < MAX_RETRIES - 1:
                    wait_seconds = (2 ** attempt) + random.uniform(0.2, 0.8)
                    print(
                        f"[FitBuddy] {model_name} temporarily unavailable. "
                        f"Retrying in {wait_seconds:.1f}s..."
                    )
                    time.sleep(wait_seconds)

        print(f"[FitBuddy] Switching model after failures on {model_name}.")

    raise RuntimeError(f"Gemini service unavailable after retries: {last_error}")


def local_fallback_plan(data):
    intensity = data["intensity"]
    if intensity == "Low":
        sets, cardio = "2", "20 minutes"
    elif intensity == "High":
        sets, cardio = "4", "35 minutes"
    else:
        sets, cardio = "3", "25 minutes"

    templates = [
        ("Full-body foundation", [
            ("Bodyweight squats", sets, "10-12"),
            ("Wall or incline push-ups", sets, "8-12"),
            ("Glute bridges", sets, "12-15"),
            ("Bird-dog", sets, "8 each side"),
        ]),
        ("Cardio & mobility", [
            ("Brisk walk / easy cycling", "1", cardio),
            ("Standing knee raises", sets, "12 each side"),
            ("Calf raises", sets, "15"),
        ]),
        ("Upper-body & core", [
            ("Incline push-ups", sets, "8-12"),
            ("Backpack rows", sets, "10-12"),
            ("Shoulder taps", sets, "8 each side"),
            ("Dead bug", sets, "8 each side"),
        ]),
        ("Active recovery", [
            ("Easy walk", "1", "20-30 minutes"),
            ("Gentle mobility flow", "1", "10 minutes"),
        ]),
        ("Lower-body strength", [
            ("Chair squats", sets, "10-12"),
            ("Reverse lunges or supported split squats", sets, "8 each side"),
            ("Glute bridges", sets, "12-15"),
            ("Calf raises", sets, "15"),
        ]),
        ("Cardio intervals", [
            ("Easy warm-up walk", "1", "5 minutes"),
            ("Brisk/easy intervals", "6", "1 min brisk + 1 min easy"),
            ("Easy walk", "1", "5 minutes"),
        ]),
        ("Recovery & reset", [
            ("Relaxed walk", "1", "15-25 minutes"),
            ("Full-body stretching", "1", "10 minutes"),
        ]),
    ]

    days = []
    for i, (focus, exercises) in enumerate(templates, start=1):
        days.append({
            "day": f"Day {i}",
            "focus": focus,
            "duration": "25-45 minutes",
            "warmup": [
                "Easy marching or walking - 3 minutes",
                "Arm circles and hip circles - 2 minutes",
            ],
            "workout": [
                {"exercise": ex, "sets": st, "reps": rep}
                for ex, st, rep in exercises
            ],
            "cooldown": [
                "Slow breathing - 1 minute",
                "Gentle stretching - 4-5 minutes",
            ],
            "recovery": "Hydrate, eat balanced meals, and aim for consistent sleep.",
        })

    return {
        "summary": (
            f"A {data['intensity'].lower()}-intensity 7-day plan focused on "
            f"{data['goal'].lower()}. This local backup plan is shown because "
            "the AI service was temporarily unavailable."
        ),
        "days": days,
        "safety_note": (
            "General wellness guidance only. Stop if you feel unwell, dizzy, "
            "short of breath beyond normal exertion, or have unusual pain."
        ),
    }


def save_history(data, plan, source, model_used):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO workout_history
            (user_id, name, age, weight, goal, intensity, source, model_used, created_at, plan_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["user_id"],
                data["name"],
                data["age"],
                data["weight"],
                data["goal"],
                data["intensity"],
                source,
                model_used,
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(plan),
            ),
        )


@app.route("/")
def home():
    return redirect(url_for("generate_workout"))


@app.route("/generate-workout", methods=["GET", "POST"])
def generate_workout():
    plan = None
    user = None
    source = None
    model_used = None

    if request.method == "POST":
        user, errors = validate_form(request.form)

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "generate_workout.html",
                goals=GOALS,
                intensities=INTENSITIES,
                form=request.form,
                plan=None,
                user=user,
            )

        try:
            plan, model_used = call_gemini(user)
            source = "Gemini AI"
            flash("Your 7-day plan was generated successfully.", "success")

        except Exception as exc:
            print(f"[FitBuddy] Gemini error: {exc}")

            if OFFLINE_FALLBACK:
                plan = local_fallback_plan(user)
                source = "Local backup plan"
                model_used = None
                flash(
                    "Gemini is temporarily unavailable, so FitBuddy generated a safe local backup plan. You can retry AI generation later.",
                    "warning",
                )
            else:
                flash(
                    "AI service is temporarily busy. Please try again in a few seconds.",
                    "error",
                )
                return render_template(
                    "generate_workout.html",
                    goals=GOALS,
                    intensities=INTENSITIES,
                    form=request.form,
                    plan=None,
                    user=user,
                )

        save_history(user, plan, source, model_used)

    return render_template(
        "generate_workout.html",
        goals=GOALS,
        intensities=INTENSITIES,
        form=request.form if request.method == "POST" else {},
        plan=plan,
        user=user,
        source=source,
        model_used=model_used,
    )


@app.route("/history")
def history():
    user_id = request.args.get("user_id", "").strip()

    with get_db() as conn:
        if user_id:
            rows = conn.execute(
                """
                SELECT id, user_id, name, goal, intensity, source, model_used, created_at
                FROM workout_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 25
                """,
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, user_id, name, goal, intensity, source, model_used, created_at
                FROM workout_history
                ORDER BY id DESC
                LIMIT 25
                """
            ).fetchall()

    return render_template("history.html", rows=rows, user_id=user_id)


@app.route("/history/<int:record_id>")
def history_detail(record_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM workout_history WHERE id = ?",
            (record_id,),
        ).fetchone()

    if row is None:
        flash("Workout record not found.", "error")
        return redirect(url_for("history"))

    plan = json.loads(row["plan_json"])
    user = {
        "user_id": row["user_id"],
        "name": row["name"],
        "age": row["age"],
        "weight": row["weight"],
        "goal": row["goal"],
        "intensity": row["intensity"],
    }

    return render_template(
        "plan_detail.html",
        plan=plan,
        user=user,
        source=row["source"],
        model_used=row["model_used"],
        created_at=row["created_at"],
    )


if __name__ == "__main__":
    init_db()
    print("FitBuddy is starting...")
    print("Open: http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=True)
