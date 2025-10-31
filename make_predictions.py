# make_predictions.py
# Reads november_games.csv and writes predictions.csv for Excel to ingest.
# Baseline: uses rating columns if available; otherwise produces neutral 50/50.
# Also emits join keys you already use in Excel (HomeAwayKey, HomeAwayKeyNorm).

import csv, math, os
from datetime import datetime

IN_CSV  = os.getenv("INPUT_CSV",  "november_games.csv")
OUT_CSV = os.getenv("OUTPUT_CSV", "predictions.csv")

def norm_key(s: str) -> str:
    # Uppercase alnum only (drop spaces/punct) → matches your Excel normalization
    return "".join(ch for ch in s.upper() if ch.isalnum())

def logistic_from_diff(diff: float, scale: float = 10.0) -> float:
    # Convert a rating difference into a win prob via logistic
    # scale=10 means ~10 pts of rating ~ 76% win prob; tweak as desired
    return 1.0 / (1.0 + math.exp(-(diff) / scale))

def try_float(row, *names, default=None):
    for n in names:
        if n in row and row[n].strip() != "":
            try:
                return float(row[n])
            except:
                pass
    return default

def main():
    rows = []
    if not os.path.exists(IN_CSV):
        raise FileNotFoundError(f"Could not find {IN_CSV} in repo root.")

    with open(IN_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    out = []
    for r in rows:
        date_raw   = r.get("Date", "")
        home_team  = r.get("HomeTeam") or r.get("Home Team") or r.get("Home")
        away_team  = r.get("AwayTeam") or r.get("Away Team") or r.get("Away")

        # Build join keys
        home_away_key     = f"{home_team}_{away_team}"
        home_away_keynorm = norm_key(home_away_key)

        # Try to pull any rating-based signals if your CSV exported them
        # Common ones in your sheet: KenPomHomeScore / KenPomAwayScore (or similar)
        home_rating = try_float(r, "KenPomHomeScore", "HomeRating", "Home_Power_Rating")
        away_rating = try_float(r, "KenPomAwayScore", "AwayRating", "Away_Power_Rating")

        # If no ratings, you could also try spreads if they’re present:
        # Convention: negative = favorite
        home_spread = try_float(r, "Home_Spread_Point", "HomeSpread", "home_spread")
        away_spread = try_float(r, "Away_Spread_Point", "AwaySpread", "away_spread")

        # Baseline probabilities
        if home_rating is not None and away_rating is not None:
            diff = home_rating - away_rating
            home_prob = logistic_from_diff(diff, scale=10.0)
        elif (home_spread is not None) and (away_spread is not None):
            # translate spread to prob loosely (bigger magnitude → higher prob)
            # We invert because negative favors home; use magnitude difference
            # Example heuristic: prob ~ logistic( -home_spread , scale=6 )
            home_prob = logistic_from_diff(-home_spread, scale=6.0)
        else:
            home_prob = 0.5

        away_prob = 1.0 - home_prob
        fav_team  = home_team if home_prob >= away_prob else away_team
        fav_prob  = max(home_prob, away_prob)

        out.append({
            "Date": date_raw,
            "HomeTeam": home_team,
            "AwayTeam": away_team,
            "HomeAwayKey": home_away_key,
            "HomeAwayKeyNorm": home_away_keynorm,
            "HomeProb": round(home_prob, 4),
            "AwayProb": round(away_prob, 4),
            "FavTeam": fav_team,
            "FavProb": round(fav_prob, 4),
            "GeneratedAtUTC": datetime.utcnow().isoformat(timespec="seconds") + "Z"
        })

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    print(f"Wrote {OUT_CSV} with {len(out)} rows.")

if __name__ == "__main__":
    main()
