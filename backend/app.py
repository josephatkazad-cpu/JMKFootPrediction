import os
import math
import statistics
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify, request

try:
    from flask_cors import CORS
except ImportError:
    CORS = None


# ============================================================
# JMK PREDICTION FOOT — BACKEND V2.2
# ============================================================

app = Flask(__name__)

if CORS:
    CORS(app)

API_URL = "https://v3.football.api-sports.io"

TOKEN = (
    os.getenv("API_FOOTBALL_KEY")
    or os.getenv("SPORTMONKS_TOKEN")
    or ""
).strip()

TIMEOUT = 20


# ============================================================
# OUTILS GÉNÉRAUX
# ============================================================

def is_available(value):
    return value is not None and value != ""


def number_or_none(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def int_or_none(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_name(value):
    if value is None or value == "":
        return "Non disponible"
    return str(value)


def safe_api(endpoint, params=None):
    """
    Appel sécurisé à API-Football.
    Retourne [] en cas d'erreur afin que l'application
    puisse continuer à fonctionner avec les données disponibles.
    """
    if not TOKEN:
        return []

    headers = {
        "x-apisports-key": TOKEN
    }

    try:
        response = requests.get(
            API_URL + endpoint,
            headers=headers,
            params=params or {},
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            return []

        data = response.json()

        if not isinstance(data, dict):
            return []

        return data.get("response", []) or []

    except Exception:
        return []


def api(endpoint, params=None):
    return safe_api(endpoint, params)


# ============================================================
# POISSON
# ============================================================

def poisson(lmbda, k):
    try:
        if lmbda is None:
            return 0.0

        lmbda = max(0.01, float(lmbda))

        return (
            math.exp(-lmbda)
            * (lmbda ** k)
            / math.factorial(k)
        )

    except Exception:
        return 0.0


def percentage(value):
    try:
        return round(float(value) * 100, 1)
    except Exception:
        return None


# ============================================================
# NORMALISATION DES PROBABILITÉS
# ============================================================

def normalize_probabilities(home, draw, away):
    values = [
        max(0.0, float(home or 0)),
        max(0.0, float(draw or 0)),
        max(0.0, float(away or 0))
    ]

    total = sum(values)

    if total <= 0:
        return 33.3, 33.4, 33.3

    return (
        round(values[0] / total * 100, 1),
        round(values[1] / total * 100, 1),
        round(values[2] / total * 100, 1)
    )


# ============================================================
# FIXTURE
# ============================================================

def get_fixture(fixture_id):
    fixtures = api(
        "/fixtures",
        {
            "id": fixture_id
        }
    )

    if not fixtures:
        return None

    return fixtures[0]


# ============================================================
# STATISTIQUES DU MATCH
# ============================================================

def get_fixture_statistics(fixture_id, home_id, away_id):
    data = api(
        "/fixtures/statistics",
        {
            "fixture": fixture_id
        }
    )

    result = {
        "domicile": {},
        "exterieur": {}
    }

    for item in data:
        team = item.get("team") or {}
        team_id = team.get("id")

        stats = {}

        for stat in item.get("statistics", []) or []:
            key = stat.get("type")
            value = stat.get("value")

            if key:
                stats[key] = value

        if team_id == home_id:
            result["domicile"] = stats

        elif team_id == away_id:
            result["exterieur"] = stats

    return result


def stat_value(stats, *names):
    for name in names:
        if name in stats:
            value = stats[name]

            if value is not None and value != "":
                return value

    return None


def clean_percentage(value):
    if value is None:
        return None

    if isinstance(value, str):
        value = value.replace("%", "").strip()

    return number_or_none(value)


# ============================================================
# CLASSEMENT
# ============================================================

def get_standings(league_id, season, home_id, away_id):
    data = api(
        "/standings",
        {
            "league": league_id,
            "season": season
        }
    )

    result = {
        "domicile": None,
        "domicile_points": None,
        "exterieur": None,
        "exterieur_points": None
    }

    if not data:
        return result

    try:
        league_data = data[0].get("league", {})
        standings_groups = league_data.get("standings", [])

        rows = []

        for group in standings_groups:
            if isinstance(group, list):
                rows.extend(group)

        for row in rows:
            team = row.get("team", {})
            team_id = team.get("id")

            rank = row.get("rank")
            points = row.get("points")

            if team_id == home_id:
                result["domicile"] = rank
                result["domicile_points"] = points

            elif team_id == away_id:
                result["exterieur"] = rank
                result["exterieur_points"] = points

    except Exception:
        pass

    return result


# ============================================================
# DERNIERS MATCHS
# ============================================================

def get_last_matches(team_id, league_id=None, season=None):
    params = {
        "team": team_id,
        "last": 5
    }

    if league_id:
        params["league"] = league_id

    if season:
        params["season"] = season

    data = api(
        "/fixtures",
        params
    )

    matches = []

    for fixture in data:
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        home_id = home.get("id")
        away_id = away.get("id")

        home_goals = goals.get("home")
        away_goals = goals.get("away")

        if (
            home_goals is None
            or away_goals is None
        ):
            continue

        if team_id == home_id:
            gf = home_goals
            ga = away_goals

            if gf > ga:
                result = "V"
            elif gf == ga:
                result = "N"
            else:
                result = "D"

            opponent = away.get("name")

        elif team_id == away_id:
            gf = away_goals
            ga = home_goals

            if gf > ga:
                result = "V"
            elif gf == away_goals:
                result = "N"
            else:
                result = "D"

            opponent = home.get("name")

        else:
            continue

        matches.append({
            "resultat": result,
            "buts_marques": gf,
            "buts_encaisses": ga,
            "adversaire": safe_name(opponent),
            "date": fixture.get("fixture", {}).get("date")
        })

    return matches[:5]


# ============================================================
# H2H
# ============================================================

def get_h2h(home_id, away_id):
    data = api(
        "/fixtures/headtohead",
        {
            "h2h": f"{home_id}-{away_id}",
            "last": 5
        }
    )

    result = []

    for fixture in data:
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        result.append({
            "domicile": safe_name(home.get("name")),
            "exterieur": safe_name(away.get("name")),
            "buts_domicile": goals.get("home"),
            "buts_exterieur": goals.get("away"),
            "date": fixture.get("fixture", {}).get("date")
        })

    return result


# ============================================================
# CALCUL DE LA FORME
# ============================================================

def form_score(matches):
    if not matches:
        return None

    points = {
        "V": 3,
        "N": 1,
        "D": 0
    }

    values = [
        points.get(match.get("resultat"), 0)
        for match in matches
    ]

    return round(
        sum(values) / (len(values) * 3) * 100,
        1
    )


def average_goals(matches, key):
    values = []

    for match in matches:
        value = number_or_none(match.get(key))

        if value is not None:
            values.append(value)

    if not values:
        return None

    return round(sum(values) / len(values), 2)


# ============================================================
# EXPECTED GOALS
# ============================================================

def expected_goals(
    home_matches,
    away_matches,
    home_stats,
    away_stats,
    h2h
):
    """
    Calcul robuste des buts attendus.

    Priorité :
    1. Forme récente
    2. Statistiques disponibles
    3. H2H
    4. Valeur neutre
    """

    home_attack = average_goals(
        home_matches,
        "buts_marques"
    )

    home_defence = average_goals(
        home_matches,
        "buts_encaisses"
    )

    away_attack = average_goals(
        away_matches,
        "buts_marques"
    )

    away_defence = average_goals(
        away_matches,
        "buts_encaisses"
    )

    home_values = []
    away_values = []

    if home_attack is not None:
        home_values.append(home_attack)

    if away_defence is not None:
        home_values.append(away_defence)

    if away_attack is not None:
        away_values.append(away_attack)

    if home_defence is not None:
        away_values.append(home_defence)

    # Statistiques de tirs cadrés
    home_sot = stat_value(
        home_stats,
        "Shots on Goal",
        "Shots on Target"
    )

    away_sot = stat_value(
        away_stats,
        "Shots on Goal",
        "Shots on Target"
    )

    home_sot = number_or_none(home_sot)
    away_sot = number_or_none(away_sot)

    if home_sot is not None:
        home_values.append(
            min(3.5, home_sot / 4.5)
        )

    if away_sot is not None:
        away_values.append(
            min(3.5, away_sot / 4.5)
        )

    # H2H
    if h2h:
        h2h_home = []
        h2h_away = []

        for match in h2h:
            hg = number_or_none(
                match.get("buts_domicile")
            )
            ag = number_or_none(
                match.get("buts_exterieur")
            )

            if hg is not None:
                h2h_home.append(hg)

            if ag is not None:
                h2h_away.append(ag)

        if h2h_home:
            home_values.append(
                sum(h2h_home) / len(h2h_home)
            )

        if h2h_away:
            away_values.append(
                sum(h2h_away) / len(h2h_away)
            )

    if home_values:
        home_xg = sum(home_values) / len(home_values)
    else:
        home_xg = 1.20

    if away_values:
        away_xg = sum(away_values) / len(away_values)
    else:
        away_xg = 1.10

    # Avantage domicile modéré
    home_xg += 0.12

    home_xg = max(0.20, min(3.50, home_xg))
    away_xg = max(0.20, min(3.50, away_xg))

    return round(home_xg, 2), round(away_xg, 2)


# ============================================================
# MATRICE DES SCORES
# ============================================================

def score_matrix(home_xg, away_xg):
    matrix = []

    for home_goals in range(0, 9):
        row = []

        for away_goals in range(0, 9):
            probability = (
                poisson(home_xg, home_goals)
                * poisson(away_xg, away_goals)
            )

            row.append(probability)

        matrix.append(row)

    return matrix


# ============================================================
# PROBABILITÉS 1X2
# ============================================================

def calculate_1x2(matrix):
    home = 0.0
    draw = 0.0
    away = 0.0

    for h in range(len(matrix)):
        for a in range(len(matrix[h])):
            value = matrix[h][a]

            if h > a:
                home += value
            elif h == a:
                draw += value
            else:
                away += value

    return normalize_probabilities(
        home,
        draw,
        away
    )


# ============================================================
# OVER / UNDER
# ============================================================

def calculate_over_under(matrix):
    totals = {
        1.5: 0.0,
        2.5: 0.0,
        3.5: 0.0
    }

    total_btts_yes = 0.0

    for h in range(len(matrix)):
        for a in range(len(matrix[h])):
            probability = matrix[h][a]

            total = h + a

            if total >= 2:
                totals[1.5] += probability

            if total >= 3:
                totals[2.5] += probability

            if total >= 4:
                totals[3.5] += probability

            if h >= 1 and a >= 1:
                total_btts_yes += probability

    return {
        "over_1_5": percentage(totals[1.5]),
        "under_1_5": percentage(1 - totals[1.5]),
        "over_2_5": percentage(totals[2.5]),
        "under_2_5": percentage(1 - totals[2.5]),
        "over_3_5": percentage(totals[3.5]),
        "under_3_5": percentage(1 - totals[3.5]),
        "btts_oui": percentage(total_btts_yes),
        "btts_non": percentage(1 - total_btts_yes)
    }


# ============================================================
# SCORES EXACTS
# ============================================================

def top_exact_scores(matrix, limit=5):
    scores = []

    for h in range(len(matrix)):
        for a in range(len(matrix[h])):
            scores.append({
                "score": f"{h}-{a}",
                "probabilite": matrix[h][a] * 100
            })

    scores.sort(
        key=lambda x: x["probabilite"],
        reverse=True
    )

    return [
        {
            "score": item["score"],
            "probabilite": round(
                item["probabilite"],
                1
            )
        }
        for item in scores[:limit]
    ]


# ============================================================
# PRÉDICTION FINALE INTELLIGENTE
# ============================================================

def final_prediction(
    home_name,
    away_name,
    home_probability,
    draw_probability,
    away_probability,
    data_quality
):
    probabilities = {
        "home": home_probability,
        "draw": draw_probability,
        "away": away_probability
    }

    ordered = sorted(
        probabilities.items(),
        key=lambda item: item[1],
        reverse=True
    )

    first = ordered[0]
    second = ordered[1]

    difference = first[1] - second[1]

    # Très peu de données
    if data_quality < 35:
        if difference < 7:
            return "Match équilibré"

    # Probabilités presque identiques
    if difference < 3:
        return "Match équilibré"

    if first[0] == "home":
        return f"Victoire {home_name}"

    if first[0] == "away":
        return f"Victoire {away_name}"

    return "Match nul"


# ============================================================
# QUALITÉ DES DONNÉES
# ============================================================

def calculate_data_quality(
    home_matches,
    away_matches,
    standings,
    h2h,
    fixture_stats
):
    score = 0
    maximum = 100

    # Forme
    if home_matches:
        score += 15

    if away_matches:
        score += 15

    # Classement
    if standings.get("domicile") is not None:
        score += 10

    if standings.get("exterieur") is not None:
        score += 10

    # H2H
    if h2h:
        score += 10

    # Statistiques du match
    home_stats = fixture_stats.get("domicile", {})
    away_stats = fixture_stats.get("exterieur", {})

    useful_home = 0
    useful_away = 0

    useful_keys = [
        "Shots on Goal",
        "Shots on Target",
        "Total Shots",
        "Ball Possession",
        "Corner Kicks",
        "Fouls",
        "Yellow Cards"
    ]

    for key in useful_keys:
        if is_available(home_stats.get(key)):
            useful_home += 1

        if is_available(away_stats.get(key)):
            useful_away += 1

    score += min(10, useful_home * 1.5)
    score += min(10, useful_away * 1.5)

    return round(
        min(max(score, 0), maximum),
        1
    )


# ============================================================
# FORMAT DES STATISTIQUES
# ============================================================

def formatted_statistics(stats):
    if not stats:
        return {
            "cartons_jaunes": None,
            "cartons_rouges": None,
            "corners": None,
            "fautes": None,
            "hors_jeu": None,
            "possession": None,
            "tirs": None,
            "tirs_bloques": None,
            "tirs_cadres": None,
            "tirs_non_cadres": None
        }

    return {
        "cartons_jaunes": stat_value(
            stats,
            "Yellow Cards"
        ),
        "cartons_rouges": stat_value(
            stats,
            "Red Cards"
        ),
        "corners": stat_value(
            stats,
            "Corner Kicks"
        ),
        "fautes": stat_value(
            stats,
            "Fouls"
        ),
        "hors_jeu": stat_value(
            stats,
            "Offsides"
        ),
        "possession": stat_value(
            stats,
            "Ball Possession"
        ),
        "tirs": stat_value(
            stats,
            "Total Shots"
        ),
        "tirs_bloques": stat_value(
            stats,
            "Blocked Shots"
        ),
        "tirs_cadres": stat_value(
            stats,
            "Shots on Goal",
            "Shots on Target"
        ),
        "tirs_non_cadres": stat_value(
            stats,
            "Shots off Goal"
        )
    }


# ============================================================
# ENDPOINT STATUS
# ============================================================

@app.route("/api/status")
def status():
    return jsonify({
        "ok": True,
        "app": "JMK Prediction Foot",
        "service": "API-Football",
        "tokenConfigured": bool(TOKEN),
        "version": "2.2.0"
    })


# ============================================================
# ENDPOINT FIXTURES
# ============================================================

@app.route("/api/fixtures")
def fixtures():
    date = request.args.get("date")

    if not date:
        date = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d")

    data = api(
        "/fixtures",
        {
            "date": date
        }
    )

    matches = []

    for fixture in data:
        fixture_data = fixture.get("fixture", {})
        league = fixture.get("league", {})
        teams = fixture.get("teams", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        timestamp = fixture_data.get("timestamp")

        if timestamp:
            dt = datetime.fromtimestamp(
                timestamp,
                timezone.utc
            )

            date_utc = dt.isoformat()
           
