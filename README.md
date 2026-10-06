# FitBuddy — AI Fitness Planner (NM Project)

FitBuddy is a Flask + Gemini API mini-project that creates a practical 7-day
activity and recovery plan from a user's age, weight, goal and intensity.

This version is designed to avoid the common raw Gemini `503 UNAVAILABLE /
high demand` error appearing on the webpage.

## Main features

- Modern responsive FitBuddy UI
- User ID, name, age, weight, goal and intensity form
- Gemini AI generated 7-day plan
- Automatic retry for temporary `503` and `429` API failures
- Automatic fallback from `gemini-3.8-flash` to `gemini-3.5-flash-lite`
- Optional local backup workout if the Gemini service is temporarily unavailable
- SQLite workout history
- Friendly error messages instead of raw API stack/error text

## Requirements

- Windows 10/11 (the included `run.bat` is for Windows)
- Python 3.10 or newer
- Internet connection
- Gemini API key from Google AI Studio

## Easiest way to run on Windows

1. Extract the ZIP.
2. Open the extracted `FitBuddy_NM_Project` folder.
3. Double-click `run.bat`.
4. On the first run, the script installs the required Python packages.
5. It creates `.env` and opens it in Notepad.
6. Replace:

   `GEMINI_API_KEY=PASTE_YOUR_GEMINI_API_KEY_HERE`

   with your own Gemini API key.

7. Save and close Notepad.
8. Return to the command window and press any key.
9. FitBuddy starts at:

   `http://127.0.0.1:5050/generate-workout`

## Manual run

Open Command Prompt inside the project folder:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
python app.py
```

Then open:

`http://127.0.0.1:5050/generate-workout`

## Important API-key rule

Do not share your `.env` file or your Gemini API key with anyone.

The ZIP contains only `.env.example`; it does NOT contain a real API key.

## 503 error handling

The app tries the primary model first. If Gemini returns a temporary 503,
high-demand, overload, rate-limit, or similar retryable error:

1. It waits briefly.
2. It retries with exponential backoff.
3. If necessary, it switches to the fallback Gemini model.
4. If Gemini is still unavailable and `OFFLINE_FALLBACK=true`, it produces a
   local backup plan so your project demonstration does not fail.

You can turn the local backup off by setting this in `.env`:

`OFFLINE_FALLBACK=false`

## Models

Defaults in `.env.example`:

- `gemini-3.8-flash`
- `gemini-3.5-flash-lite`

You can change them later without editing Python code.

## Project structure

```text
FitBuddy_NM_Project/
│
├── app.py
├── requirements.txt
├── .env.example
├── run.bat
├── run.ps1
├── README.md
│
├── templates/
│   ├── base.html
│   ├── generate_workout.html
│   ├── history.html
│   └── plan_detail.html
│
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

`fitbuddy.db` is created automatically the first time the app runs.

## Troubleshooting

### Python is not found

Install Python from python.org and enable **Add Python to PATH** during installation.

### API key missing

Open `.env` and make sure the line is:

`GEMINI_API_KEY=your_actual_key_here`

Do not add extra quotation marks unless they are actually part of the key.

### Gemini still returns 503

A 503 can be a temporary server-capacity issue. This application already retries,
uses a fallback model, and optionally supplies a local backup plan. Wait a short
time and retry if you specifically need a Gemini-generated result.

### Port 5050 already in use

Close any previous Flask/Python terminal that is already running the project,
then run `run.bat` again.

## Academic note

The workout content is general wellness guidance only and should not be presented
as medical diagnosis or treatment.
