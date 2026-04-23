# Golf Strokes Gained Analyzer

A simple Flask web app for an AI105 data-analysis final project.

## What it does
- Accepts one round of user-entered golf stats
- Estimates strokes gained for:
  - Off the Tee
  - Approach
  - Around the Green
  - Putting
- Applies a dependency-adjusted training-priority model
- Recommends the single area most likely to improve scoring

## Files
- `app.py` – Flask website
- `calculator.py` – strokes-gained and training-priority model
- `baseline_data.json` – editable PGA-style benchmark values
- `templates/index.html` – front-end page
- `static/style.css` – styling

## How to run
```bash
pip install -r requirements.txt
python app.py
```

Then open the local URL Flask prints in the terminal, usually `http://127.0.0.1:5000`.

## Model notes
This project reports **estimated** strokes gained from round-level stats. It does **not** compute true ShotLink shot-by-shot strokes gained.

Dependency logic:
- Off the Tee can inherit some Approach blame when fairway rate is poor.
- Approach can inherit some Around-the-Green blame when GIR is poor.
- Putting stays independent.

## Updating the PGA baseline
Edit `baseline_data.json` and replace the starter benchmark values with exact current PGA Tour averages before your final submission.


## Hybrid model update
- Handicap benchmarks set expected score and handicap-scaled strokes gained.
- PGA Tour benchmarks are retained for practice-priority scoring and coaching recommendations so the weakest-area output stays sensitive and realistic.


## Deploy to Render
1. Create a new GitHub repository and upload this entire folder.
2. Sign in to Render and choose **New > Blueprint** or **New > Web Service**.
3. If you use the included `render.yaml`, Render can auto-fill the service settings.
4. If you create the service manually, use:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. After the deploy finishes, your app will be live at your `onrender.com` URL.

Render documents this Flask setup with Python 3, `pip install -r requirements.txt`, and `gunicorn app:app`.
