from __future__ import annotations

from flask import Flask, render_template, request

from calculator import compute_model, load_baseline

app = Flask(__name__)

BASELINE = load_baseline()

DEFAULT_FORM = {
    "round_score": 84,
    "handicap": 12,
    "fairways_hit": 6,
    "fairway_opportunities": 14,
    "driving_distance": 255,
    "tee_penalties": 1,
    "gir_hit": 8,
    "gir_opportunities": 18,
    "approach_penalties": 0,
    "updown_pct": 42,
    "one_putts": 4,
    "two_putts": 11,
    "three_putts": 3,
    "holes_with_putts": 18,
}


def parse_float(name: str) -> float:
    return float(request.form.get(name, 0) or 0)


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    form = DEFAULT_FORM.copy()

    if request.method == "POST":
        try:
            form = {key: parse_float(key) for key in DEFAULT_FORM}

            if form["round_score"] <= 0:
                raise ValueError("Round score must be greater than zero.")
            if form["handicap"] < -10 or form["handicap"] > 54:
                raise ValueError("Handicap must be between -10 and 54.")
            if form["fairway_opportunities"] <= 0 or form["gir_opportunities"] <= 0 or form["holes_with_putts"] <= 0:
                raise ValueError("Opportunity fields must be greater than zero.")
            if form["one_putts"] + form["two_putts"] + form["three_putts"] > form["holes_with_putts"]:
                raise ValueError("1-putts + 2-putts + 3-putts cannot exceed holes with putts.")

            result = compute_model(form, BASELINE)
        except ValueError as exc:
            error = str(exc)

    return render_template("index.html", result=result, error=error, form=form)


if __name__ == "__main__":
    app.run(debug=True)
