from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

BASELINE_PATH = Path(__file__).with_name("baseline_data.json")
CATEGORY_KEYS = ["Off the Tee", "Approach", "Around the Green", "Putting"]


def load_baseline() -> Dict[str, Any]:
    with BASELINE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def loss(x: float) -> float:
    return max(0.0, -x)


def calc_dependency_weights(fairway_pct: float, gir_pct: float) -> tuple[float, float]:
    if fairway_pct < 0.35:
        alpha = 0.40
    elif fairway_pct < 0.50:
        alpha = 0.20
    else:
        alpha = 0.0

    if gir_pct < 0.35:
        beta = 0.35
    elif gir_pct < 0.50:
        beta = 0.15
    else:
        beta = 0.0

    return alpha, beta


def category_analysis(name: str, sg: float, priority: float) -> str:
    if sg >= 1.0:
        base = f"{name} was a clear strength this round and added strokes to your overall performance."
    elif sg >= 0.0:
        base = f"{name} held up well and was at least neutral to slightly positive."
    elif sg > -1.0:
        base = f"{name} cost a little this round, but it was not the main issue."
    else:
        base = f"{name} was a major leak this round and cost multiple tenths to full strokes."

    if priority >= 2.0:
        focus = "This should be a top practice priority."
    elif priority >= 1.0:
        focus = "This deserves meaningful practice time soon."
    elif priority > 0.0:
        focus = "This needs maintenance, but not all of your practice time."
    else:
        focus = "No immediate practice emphasis is needed here."

    return f"{base} {focus}"


def interpolate_benchmark(handicap: float, baseline: Dict[str, Any]) -> Dict[str, float]:
    table = {float(k): v for k, v in baseline["handicap_benchmarks"].items()}
    keys = sorted(table)
    h = clamp(handicap, keys[0], keys[-1])

    if h <= keys[0]:
        return dict(table[keys[0]])
    if h >= keys[-1]:
        return dict(table[keys[-1]])

    for low, high in zip(keys, keys[1:]):
        if low <= h <= high:
            if h == low:
                return dict(table[low])
            if h == high:
                return dict(table[high])
            t = (h - low) / (high - low)
            out: Dict[str, float] = {}
            for stat in table[low]:
                out[stat] = table[low][stat] + t * (table[high][stat] - table[low][stat])
            return out

    return dict(table[keys[-1]])


def scale_categories_to_target(raw: Dict[str, float], target_total: float) -> Dict[str, float]:
    """Adjust category values to match the score-based total without forcing all signs.

    Start with the raw handicap signal in each category, then distribute the gap to the
    score-based target total across categories that already point in the needed direction.
    This keeps obvious weaknesses negative and obvious strengths positive whenever possible.
    """
    raw_total = sum(raw[key] for key in CATEGORY_KEYS)
    scaled = {key: float(raw[key]) for key in CATEGORY_KEYS}
    delta = target_total - raw_total

    if abs(delta) < 1e-9:
        scaled["Total"] = round(raw_total, 2)
        return {key: round(value, 2) for key, value in scaled.items()}

    if delta > 0:
        evidence = {key: max(0.0, raw[key]) for key in CATEGORY_KEYS}
    else:
        evidence = {key: max(0.0, -raw[key]) for key in CATEGORY_KEYS}

    total_evidence = sum(evidence.values())
    if total_evidence < 1e-9:
        evidence = {key: abs(raw[key]) for key in CATEGORY_KEYS}
        total_evidence = sum(evidence.values())

    if total_evidence < 1e-9:
        equal_share = target_total / len(CATEGORY_KEYS)
        scaled = {key: equal_share for key in CATEGORY_KEYS}
        scaled["Total"] = target_total
        return {key: round(value, 2) for key, value in scaled.items()}

    for key in CATEGORY_KEYS:
        scaled[key] += delta * evidence[key] / total_evidence

    scaled["Total"] = sum(scaled[key] for key in CATEGORY_KEYS)
    return {key: round(value, 2) for key, value in scaled.items()}


def compute_pga_stat_sg(
    fairway_pct: float,
    gir_pct: float,
    updown_pct: float,
    one_putt_pct: float,
    three_putt_pct: float,
    user: Dict[str, float],
    pga: Dict[str, Any],
) -> Dict[str, float]:
    gir_benchmark = clamp(
        pga["gir_pct"]
        - pga.get("distance_adjustment_per_yard", 0.0) * max(0.0, pga["driving_distance"] - user["driving_distance"]),
        0.35,
        pga["gir_pct"],
    )

    sg_ott = (
        0.05 * ((fairway_pct - pga["fairway_pct"]) * 100.0)
        + 0.01 * (user["driving_distance"] - pga["driving_distance"])
        - 1.0 * user["tee_penalties"]
    )

    sg_app = 0.08 * ((gir_pct - gir_benchmark) * 100.0) - 1.0 * user["approach_penalties"]
    sg_arg = 0.07 * ((updown_pct - pga["updown_pct"]) * 100.0)
    sg_putt = (
        0.06 * ((one_putt_pct - pga["one_putt_pct"]) * 100.0)
        - 0.10 * ((three_putt_pct - pga["three_putt_pct"]) * 100.0)
    )

    return {
        "Off the Tee": sg_ott,
        "Approach": sg_app,
        "Around the Green": sg_arg,
        "Putting": sg_putt,
    }


def compute_model(user: Dict[str, float], baseline: Dict[str, Any]) -> Dict[str, Any]:
    handicap_benchmark = interpolate_benchmark(user.get("handicap", 0.0), baseline)
    pga = baseline["pga_baseline"]

    fairway_pct = safe_div(user["fairways_hit"], user["fairway_opportunities"])
    gir_pct = safe_div(user["gir_hit"], user["gir_opportunities"])
    one_putt_pct = safe_div(user["one_putts"], user["holes_with_putts"])
    three_putt_pct = safe_div(user["three_putts"], user["holes_with_putts"])
    updown_pct = clamp(user["updown_pct"] / 100.0, 0.0, 1.0)
    putts_per_round = user["one_putts"] + 2 * user["two_putts"] + 3 * user["three_putts"]

    handicap_signal = {
        "Off the Tee": (
            0.05 * ((fairway_pct - handicap_benchmark["fairway_pct"]) * 100.0)
            + 0.018 * (user["driving_distance"] - handicap_benchmark["driving_distance"])
            - 1.0 * user["tee_penalties"]
        ),
        "Approach": 0.09 * ((gir_pct - handicap_benchmark["gir_pct"]) * 100.0) - 1.0 * user["approach_penalties"],
        "Around the Green": 0.08 * ((updown_pct - handicap_benchmark["updown_pct"]) * 100.0),
        "Putting": (
            0.55 * (handicap_benchmark["putts_per_round"] - putts_per_round)
            + 0.03 * ((handicap_benchmark["fairway_pct"] - fairway_pct) * 100.0)
            - 0.04 * ((handicap_benchmark["gir_pct"] - gir_pct) * 100.0)
            + 0.12 * ((handicap_benchmark["updown_pct"] - updown_pct) * 100.0)
        ),
    }

    expected_score = handicap_benchmark["avg_score"]
    handicap_target_total = expected_score - user["round_score"]
    scaled_strokes_gained = scale_categories_to_target(handicap_signal, handicap_target_total)

    pga_strokes_gained_raw = compute_pga_stat_sg(
        fairway_pct=fairway_pct,
        gir_pct=gir_pct,
        updown_pct=updown_pct,
        one_putt_pct=one_putt_pct,
        three_putt_pct=three_putt_pct,
        user=user,
        pga=pga,
    )
    pga_total = sum(pga_strokes_gained_raw.values())

    alpha, beta = calc_dependency_weights(fairway_pct, gir_pct)
    train_scores = {
        "Off the Tee": loss(pga_strokes_gained_raw["Off the Tee"]) + alpha * loss(pga_strokes_gained_raw["Approach"]),
        "Approach": loss(pga_strokes_gained_raw["Approach"]) + beta * loss(pga_strokes_gained_raw["Around the Green"]),
        "Around the Green": loss(pga_strokes_gained_raw["Around the Green"]),
        "Putting": loss(pga_strokes_gained_raw["Putting"]),
    }

    strokes_gained = {key: round(scaled_strokes_gained[key], 2) for key in CATEGORY_KEYS}
    strokes_gained["Total"] = round(scaled_strokes_gained["Total"], 2)

    pga_comparison = {key: round(pga_strokes_gained_raw[key], 2) for key in CATEGORY_KEYS}
    pga_comparison["Total"] = round(pga_total, 2)

    weakest = max(train_scores, key=train_scores.get)
    strongest = max({k: v for k, v in scaled_strokes_gained.items() if k != "Total"}, key=lambda k: scaled_strokes_gained[k])

    recommendations = {
        "Off the Tee": {
            "headline": "Primary focus: off the tee",
            "details": "Your handicap-scaled score can still look fine here, but against elite stat quality this round leaked shots off the tee. Prioritize driver control, center-face contact, and penalty avoidance.",
        },
        "Approach": {
            "headline": "Primary focus: approach play",
            "details": "The score result may have been acceptable for your handicap, but the stat profile says approach play is the biggest separator. Prioritize iron distance control and GIR improvement.",
        },
        "Around the Green": {
            "headline": "Primary focus: short game",
            "details": "Your round can still score okay while short-game stats lag. Prioritize chip and pitch contact, simple carry-roll patterns, and routine up-and-down practice from standard lies.",
        },
        "Putting": {
            "headline": "Primary focus: putting",
            "details": "Putting is the clearest place to lower scores faster based on the stat quality of this round. Prioritize lag putting and short-putt conversion, especially reducing three-putts first.",
        },
    }

    analyses = [
        {
            "name": key,
            "sg": round(scaled_strokes_gained[key], 2),
            "priority": round(train_scores[key], 2),
            "text": category_analysis(key, scaled_strokes_gained[key], train_scores[key]),
        }
        for key in CATEGORY_KEYS
    ]

    return {
        "round_score": int(user["round_score"]),
        "handicap": round(user.get("handicap", 0.0), 1),
        "expected_score": round(expected_score, 1),
        "benchmark": {
            "driving_distance": round(handicap_benchmark["driving_distance"], 1),
            "fairway_pct": round(handicap_benchmark["fairway_pct"] * 100.0, 1),
            "gir_pct": round(handicap_benchmark["gir_pct"] * 100.0, 1),
            "updown_pct": round(handicap_benchmark["updown_pct"] * 100.0, 1),
            "putts_per_round": round(handicap_benchmark["putts_per_round"], 1),
        },
        "rates": {
            "fairway_pct": round(fairway_pct * 100.0, 1),
            "gir_pct": round(gir_pct * 100.0, 1),
            "updown_pct": round(updown_pct * 100.0, 1),
            "one_putt_pct": round(one_putt_pct * 100.0, 1),
            "three_putt_pct": round(three_putt_pct * 100.0, 1),
            "putts_per_round": round(putts_per_round, 1),
        },
        "strokes_gained": strokes_gained,
        "pga_comparison": pga_comparison,
        "scaled_strokes_gained": {key: round(value, 2) for key, value in scaled_strokes_gained.items()},
        "train_scores": {k: round(v, 2) for k, v in train_scores.items()},
        "weakest": weakest,
        "strongest": strongest,
        "recommendation": recommendations[weakest],
        "analyses": analyses,
    }
