import os
import math
import datetime
import requests

from flask import Flask, jsonify, request, send_from_directory

try:
    from flask_cors import CORS
except Exception:
    CORS = lambda app: None


# ============================================================
# APPLICATION
# ============================================================

app = Flask(
    __name__,
    static_folder="../frontend",
    static_url_path=""
)

CORS(app)


# ============================================================
# CONFIGURATION API-FOOTBALL
# ============================================================

API = "https://v3.football.api-sports.io"

# La clé doit être configurée sur PythonAnywhere.
# API_FOOTBALL_KEY est prioritaire.
TOKEN = (
    os.getenv("API_FOOTBALL_KEY")
    or os.getenv("SPORTMONKS_TOKEN")
    or ""
).strip()


# ============================================================
# OUTILS API
# ============================================================

def api(path):
    """
    Appelle API-Football.
    """

    if not TOKEN:
        raise RuntimeError(
            "API_FOOTBALL_KEY non configurée sur PythonAnywhere."
        )

    url = API + "/" + path

    response = requests.get(
        url,
        headers={
            "x-apisports-key": TOKEN
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    # API-Football peut retourner une erreur dans errors
    errors = data.get("errors")

    if errors:
        raise RuntimeError(str(errors))

    return data


def safe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def percentage(value, total):
    if not total:
        return None

    return round((value / total) * 100, 1)


def poisson(k, lam):
    if lam <= 0:
        return 0.0

    return math.exp(-lam) * (lam ** k) / math.factorial(k)


# ============================================================
# STATUT
# ============================================================

@app.get("/api/status")
def status():

    return jsonify(
        ok=True,
        app="JMK Prediction Foot",
        service="API-Football",
        tokenConfigured=bool(TOKEN),
        version="2.0.0"
    )


# ============================================================
# MATCHS
# ============================================================

@app.get("/api/fixtures")
def fixtures():

    date = (
        request.args.get("date")
        or datetime.date.today().isoformat()
    )

    if not TOKEN:
        return jsonify(
            ok=False,
            erreur="API_FOOTBALL_KEY non configurée."
        ), 503

    try:

        data = api(
            f"fixtures?date={date}&timezone=Europe/Paris"
        )

        matches = []

        for item in data.get("response", []):

            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            league = item.get("league", {})
            status_data = fixture.get("status", {})

            home = teams.get("home", {}) or {}
            away = teams.get("away", {}) or {}

            matches.append({
                "fixture_id": fixture.get("id"),

                "date_utc": fixture.get("date"),

                "horaire": (
                    fixture.get("date") or ""
                )[11:16],

                "pays": league.get("country"),

                "championnat": league.get("name"),

                "league_id": league.get("id"),

                "season": league.get("season"),

                "round": league.get("round"),

                "statut": status_data.get("long"),

                "code_statut": status_data.get("short"),

                "domicile": {
                    "id": home.get("id"),
                    "name": home.get("name"),
                    "logo": home.get("logo")
                },

                "exterieur": {
                    "id": away.get("id"),
                    "name": away.get("name"),
                    "logo": away.get("logo")
                }
            })

        return jsonify(
            ok=True,
            date=date,
            total=len(matches),
            matches=matches
        )

    except Exception as e:

        return jsonify(
            ok=False,
            erreur=str(e)
        ), 502


# ============================================================
# EXTRACTION STATISTIQUES
# ============================================================

def get_stat(statistics, name):

    for item in statistics or []:

        if str(item.get("type", "")).lower() == name.lower():

            value = item.get("value")

            if value is None:
                return None

            if isinstance(value, str):
                value = value.replace("%", "").strip()

            return value

    return None


def team_statistics(fixture_id, team_id):

    try:

        data = api(
            f"fixtures/statistics?fixture={fixture_id}"
        )

        for team_data in data.get("response", []):

            team = team_data.get("team", {})

            if team.get("id") == team_id:

                statistics = team_data.get("statistics", [])

                return {
                    "possession": get_stat(
                        statistics,
                        "Ball Possession"
                    ),

                    "shots": get_stat(
                        statistics,
                        "Total Shots"
                    ),

                    "shots_on_target": get_stat(
                        statistics,
                        "Shots on Goal"
                    ),

                    "shots_off_target": get_stat(
                        statistics,
                        "Shots off Goal"
                    ),

                    "blocked_shots": get_stat(
                        statistics,
                        "Blocked Shots"
                    ),

                    "corners": get_stat(
                        statistics,
                        "Corner Kicks"
                    ),

                    "fouls": get_stat(
                        statistics,
                        "Fouls"
                    ),

                    "yellow_cards": get_stat(
                        statistics,
                        "Yellow Cards"
                    ),

                    "red_cards": get_stat(
                        statistics,
                        "Red Cards"
                    ),

                    "offsides": get_stat(
                        statistics,
                        "Offsides"
                    )
                }

    except Exception:
        pass

    return {}


# ============================================================
# CLASSEMENT
# ============================================================

def get_standings(league_id, season):

    try:

        data = api(
            f"standings?league={league_id}&season={season}"
        )

        response = data.get("response", [])

        if not response:
            return []

        league = response[0].get("league", {})

        standings = league.get("standings", [])

        if standings and isinstance(standings[0], list):
            return standings[0]

        return standings

    except Exception:
        return []


def find_team_row(rows, team_id):

    for row in rows:

        team = row.get("team", {})

        if team.get("id") == team_id:
            return row

    return {}


# ============================================================
# FORME DES 5 DERNIERS MATCHS
# ============================================================

def get_last_matches(team_id):

    try:

        data = api(
            f"fixtures?team={team_id}&last=5"
            f"&timezone=Europe/Paris"
        )

        results = []

        for item in data.get("response", []):

            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})

            home = teams.get("home", {}) or {}
            away = teams.get("away", {}) or {}

            home_goals = goals.get("home")
            away_goals = goals.get("away")

            result = None

            if home_goals is not None and away_goals is not None:

                if team_id == home.get("id"):

                    if home_goals > away_goals:
                        result = "V"
                    elif home_goals == away_goals:
                        result = "N"
                    else:
                        result = "D"

                elif team_id == away.get("id"):

                    if away_goals > home_goals:
                        result = "V"
                    elif away_goals == home_goals:
                        result = "N"
                    else:
                        result = "D"

            results.append({
                "fixture_id": fixture.get("id"),

                "date": fixture.get("date"),

                "adversaire": (
                    away.get("name")
                    if team_id == home.get("id")
                    else home.get("name")
                ),

                "domicile": home.get("name"),

                "exterieur": away.get("name"),

                "score": (
                    f"{home_goals}-{away_goals}"
                    if home_goals is not None
                    and away_goals is not None
                    else None
                ),

                "resultat": result
            })

        return results

    except Exception:
        return []


# ============================================================
# H2H
# ============================================================

def get_h2h(home_id, away_id):

    try:

        data = api(
            f"fixtures/headtohead?h2h={home_id}-{away_id}&last=10"
        )

        results = []

        for item in data.get("response", []):

            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})

            home = teams.get("home", {}) or {}
            away = teams.get("away", {}) or {}

            results.append({
                "fixture_id": fixture.get("id"),

                "date": fixture.get("date"),

                "domicile": home.get("name"),

                "exterieur": away.get("name"),

                "score": (
                    f"{goals.get('home')}-{goals.get('away')}"
                    if goals.get("home") is not None
                    and goals.get("away") is not None
                    else None
                )
            })

        return results

    except Exception:
        return []


# ============================================================
# CALCUL DE BASE DES BUTS ATTENDUS
# ============================================================

def expected_goals(home_row, away_row):

    def goals_for(row):

        all_data = row.get("all", {}) or {}

        played = all_data.get("played") or 0

        goals = all_data.get("goals", {}) or {}

        scored = goals.get("for") or 0

        if played <= 0:
            return 1.20

        return scored / played

    def goals_against(row):

        all_data = row.get("all", {}) or {}

        played = all_data.get("played") or 0

        goals = all_data.get("goals", {}) or {}

        conceded = goals.get("against") or 0

        if played <= 0:
            return 1.20

        return conceded / played

    home_attack = goals_for(home_row)
    home_defence = goals_against(home_row)

    away_attack = goals_for(away_row)
    away_defence = goals_against(away_row)

    home_lambda = max(
        0.15,
        (home_attack + away_defence) / 2
    )

    away_lambda = max(
        0.15,
        (away_attack + home_defence) / 2
    )

    return home_lambda, away_lambda


# ============================================================
# ANALYSE D'UN MATCH
# ============================================================

@app.get("/api/analyze")
def analyze():

    fixture_id = request.args.get("fixture", "").strip()

    if not fixture_id.isdigit():

        return jsonify(
            ok=False,
            erreur="Identifiant de match invalide."
        ), 400

    if not TOKEN:

        return jsonify(
            ok=False,
            erreur="API_FOOTBALL_KEY non configurée."
        ), 503

    try:

        # ----------------------------------------------------
        # MATCH
        # ----------------------------------------------------

        match_data = api(
            f"fixtures?id={fixture_id}"
        )

        response = match_data.get("response", [])

        if not response:

            return jsonify(
                ok=False,
                erreur="Match introuvable."
            ), 404

        match = response[0]

        fixture = match.get("fixture", {})
        teams = match.get("teams", {})
        league = match.get("league", {})
        goals = match.get("goals", {})

        home = teams.get("home", {}) or {}
        away = teams.get("away", {}) or {}

        home_id = home.get("id")
        away_id = away.get("id")

        league_id = league.get("id")
        season = league.get("season")


        # ----------------------------------------------------
        # CLASSEMENT
        # ----------------------------------------------------

        standings = get_standings(
            league_id,
            season
        )

        home_row = find_team_row(
            standings,
            home_id
        )

        away_row = find_team_row(
            standings,
            away_id
        )


        # ----------------------------------------------------
        # FORME
        # ----------------------------------------------------

        home_form = get_last_matches(
            home_id
        )

        away_form = get_last_matches(
            away_id
        )


        # ----------------------------------------------------
        # H2H
        # ----------------------------------------------------

        h2h = get_h2h(
            home_id,
            away_id
        )


        # ----------------------------------------------------
        # STATISTIQUES DU MATCH
        # ----------------------------------------------------

        home_stats = team_statistics(
            int(fixture_id),
            home_id
        )

        away_stats = team_statistics(
            int(fixture_id),
            away_id
        )


        # ----------------------------------------------------
        # BUTS ATTENDUS
        # ----------------------------------------------------

        home_lambda, away_lambda = expected_goals(
            home_row,
            away_row
        )


        # ----------------------------------------------------
        # PROBABILITÉS 1X2 + SCORES
        # ----------------------------------------------------

        p1 = 0.0
        px = 0.0
        p2 = 0.0

        scores = []

        for h in range(0, 8):

            for a in range(0, 8):

                probability = (
                    poisson(h, home_lambda)
                    * poisson(a, away_lambda)
                )

                scores.append(
                    (
                        probability,
                        h,
                        a
                    )
                )

                if h > a:
                    p1 += probability

                elif h == a:
                    px += probability

                else:
                    p2 += probability


        total = p1 + px + p2

        if total <= 0:
            total = 1


        scores.sort(
            key=lambda x: x[0],
            reverse=True
        )


        # ----------------------------------------------------
        # OVER / UNDER
        # ----------------------------------------------------

        over_1_5 = 0
        over_2_5 = 0
        over_3_5 = 0

        btts_yes = 0

        for probability, h, a in scores:

            total_goals = h + a

            if total_goals >= 2:
                over_1_5 += probability

            if total_goals >= 3:
                over_2_5 += probability

            if total_goals >= 4:
                over_3_5 += probability

            if h >= 1 and a >= 1:
                btts_yes += probability


        # ----------------------------------------------------
        # PRÉDICTION FINALE
        # ----------------------------------------------------

        if p1 >= px and p1 >= p2:

            final_prediction = (
                f"Victoire {home.get('name')}"
            )

import os
import math
import datetime
import requests

from flask import Flask, jsonify, request, send_from_directory

try:
    from flask_cors import CORS
except Exception:
    CORS = lambda app: None


# ============================================================
# APPLICATION
# ============================================================

app = Flask(
    __name__,
    static_folder="../frontend",
    static_url_path=""
)

CORS(app)


# ============================================================
# CONFIGURATION API-FOOTBALL
# ============================================================

API = "https://v3.football.api-sports.io"

# La clé doit être configurée sur PythonAnywhere.
# API_FOOTBALL_KEY est prioritaire.
TOKEN = (
    os.getenv("API_FOOTBALL_KEY")
    or os.getenv("SPORTMONKS_TOKEN")
    or ""
).strip()


# ============================================================
# OUTILS API
# ============================================================

def api(path):
    """
    Appelle API-Football.
    """

    if not TOKEN:
        raise RuntimeError(
            "API_FOOTBALL_KEY non configurée sur PythonAnywhere."
        )

    url = API + "/" + path

    response = requests.get(
        url,
        headers={
            "x-apisports-key": TOKEN
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    # API-Football peut retourner une erreur dans errors
    errors = data.get("errors")

    if errors:
        raise RuntimeError(str(errors))

    return data


def safe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def percentage(value, total):
    if not total:
        return None

    return round((value / total) * 100, 1)


def poisson(k, lam):
    if lam <= 0:
        return 0.0

    return math.exp(-lam) * (lam ** k) / math.factorial(k)


# ============================================================
# STATUT
# ============================================================

@app.get("/api/status")
def status():

    return jsonify(
        ok=True,
        app="JMK Prediction Foot",
        service="API-Football",
        tokenConfigured=bool(TOKEN),
        version="2.0.0"
    )


# ============================================================
# MATCHS
# ============================================================

@app.get("/api/fixtures")
def fixtures():

    date = (
        request.args.get("date")
        or datetime.date.today().isoformat()
    )

    if not TOKEN:
        return jsonify(
            ok=False,
            erreur="API_FOOTBALL_KEY non configurée."
        ), 503

    try:

        data = api(
            f"fixtures?date={date}&timezone=Europe/Paris"
        )

        matches = []

        for item in data.get("response", []):

            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            league = item.get("league", {})
            status_data = fixture.get("status", {})

            home = teams.get("home", {}) or {}
            away = teams.get("away", {}) or {}

            matches.append({
                "fixture_id": fixture.get("id"),

                "date_utc": fixture.get("date"),

                "horaire": (
                    fixture.get("date") or ""
                )[11:16],

                "pays": league.get("country"),

                "championnat": league.get("name"),

                "league_id": league.get("id"),

                "season": league.get("season"),

                "round": league.get("round"),

                "statut": status_data.get("long"),

                "code_statut": status_data.get("short"),

                "domicile": {
                    "id": home.get("id"),
                    "name": home.get("name"),
                    "logo": home.get("logo")
                },

                "exterieur": {
                    "id": away.get("id"),
                    "name": away.get("name"),
                    "logo": away.get("logo")
                }
            })

        return jsonify(
            ok=True,
            date=date,
            total=len(matches),
            matches=matches
        )

    except Exception as e:

        return jsonify(
            ok=False,
            erreur=str(e)
        ), 502


# ============================================================
# EXTRACTION STATISTIQUES
# ============================================================

def get_stat(statistics, name):

    for item in statistics or []:

        if str(item.get("type", "")).lower() == name.lower():

            value = item.get("value")

            if value is None:
                return None

            if isinstance(value, str):
                value = value.replace("%", "").strip()

            return value

    return None


def team_statistics(fixture_id, team_id):

    try:

        data = api(
            f"fixtures/statistics?fixture={fixture_id}"
        )

        for team_data in data.get("response", []):

            team = team_data.get("team", {})

            if team.get("id") == team_id:

                statistics = team_data.get("statistics", [])

                return {
                    "possession": get_stat(
                        statistics,
                        "Ball Possession"
                    ),

                    "shots": get_stat(
                        statistics,
                        "Total Shots"
                    ),

                    "shots_on_target": get_stat(
                        statistics,
                        "Shots on Goal"
                    ),

                    "shots_off_target": get_stat(
                        statistics,
                        "Shots off Goal"
                    ),

                    "blocked_shots": get_stat(
                        statistics,
                        "Blocked Shots"
                    ),

                    "corners": get_stat(
                        statistics,
                        "Corner Kicks"
                    ),

                    "fouls": get_stat(
                        statistics,
                        "Fouls"
                    ),

                    "yellow_cards": get_stat(
                        statistics,
                        "Yellow Cards"
                    ),

                    "red_cards": get_stat(
                        statistics,
                        "Red Cards"
                    ),

                    "offsides": get_stat(
                        statistics,
                        "Offsides"
                    )
                }

    except Exception:
        pass

    return {}


# ============================================================
# CLASSEMENT
# ============================================================

def get_standings(league_id, season):

    try:

        data = api(
            f"standings?league={league_id}&season={season}"
        )

        response = data.get("response", [])

        if not response:
            return []

        league = response[0].get("league", {})

        standings = league.get("standings", [])

        if standings and isinstance(standings[0], list):
            return standings[0]

        return standings

    except Exception:
        return []


def find_team_row(rows, team_id):

    for row in rows:

        team = row.get("team", {})

        if team.get("id") == team_id:
            return row

    return {}


# ============================================================
# FORME DES 5 DERNIERS MATCHS
# ============================================================

def get_last_matches(team_id):

    try:

        data = api(
            f"fixtures?team={team_id}&last=5"
            f"&timezone=Europe/Paris"
        )

        results = []

        for item in data.get("response", []):

            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})

            home = teams.get("home", {}) or {}
            away = teams.get("away", {}) or {}

            home_goals = goals.get("home")
            away_goals = goals.get("away")

            result = None

            if home_goals is not None and away_goals is not None:

                if team_id == home.get("id"):

                    if home_goals > away_goals:
                        result = "V"
                    elif home_goals == away_goals:
                        result = "N"
                    else:
                        result = "D"

                elif team_id == away.get("id"):

                    if away_goals > home_goals:
                        result = "V"
                    elif away_goals == home_goals:
                        result = "N"
                    else:
                        result = "D"

            results.append({
                "fixture_id": fixture.get("id"),

                "date": fixture.get("date"),

                "adversaire": (
                    away.get("name")
                    if team_id == home.get("id")
                    else home.get("name")
                ),

                "domicile": home.get("name"),

                "exterieur": away.get("name"),

                "score": (
                    f"{home_goals}-{away_goals}"
                    if home_goals is not None
                    and away_goals is not None
                    else None
                ),

                "resultat": result
            })

        return results

    except Exception:
        return []


# ============================================================
# H2H
# ============================================================

def get_h2h(home_id, away_id):

    try:

        data = api(
            f"fixtures/headtohead?h2h={home_id}-{away_id}&last=10"
        )

        results = []

        for item in data.get("response", []):

            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})

            home = teams.get("home", {}) or {}
            away = teams.get("away", {}) or {}

            results.append({
                "fixture_id": fixture.get("id"),

                "date": fixture.get("date"),

                "domicile": home.get("name"),

                "exterieur": away.get("name"),

                "score": (
                    f"{goals.get('home')}-{goals.get('away')}"
                    if goals.get("home") is not None
                    and goals.get("away") is not None
                    else None
                )
            })

        return results

    except Exception:
        return []


# ============================================================
# CALCUL DE BASE DES BUTS ATTENDUS
# ============================================================

def expected_goals(home_row, away_row):

    def goals_for(row):

        all_data = row.get("all", {}) or {}

        played = all_data.get("played") or 0

        goals = all_data.get("goals", {}) or {}

        scored = goals.get("for") or 0

        if played <= 0:
            return 1.20

        return scored / played

    def goals_against(row):

        all_data = row.get("all", {}) or {}

        played = all_data.get("played") or 0

        goals = all_data.get("goals", {}) or {}

        conceded = goals.get("against") or 0

        if played <= 0:
            return 1.20

        return conceded / played

    home_attack = goals_for(home_row)
    home_defence = goals_against(home_row)

    away_attack = goals_for(away_row)
    away_defence = goals_against(away_row)

    home_lambda = max(
        0.15,
        (home_attack + away_defence) / 2
    )

    away_lambda = max(
        0.15,
        (away_attack + home_defence) / 2
    )

    return home_lambda, away_lambda


# ============================================================
# ANALYSE D'UN MATCH
# ============================================================

@app.get("/api/analyze")
def analyze():

    fixture_id = request.args.get("fixture", "").strip()

    if not fixture_id.isdigit():

        return jsonify(
            ok=False,
            erreur="Identifiant de match invalide."
        ), 400

    if not TOKEN:

        return jsonify(
            ok=False,
            erreur="API_FOOTBALL_KEY non configurée."
        ), 503

    try:

        # ----------------------------------------------------
        # MATCH
        # ----------------------------------------------------

        match_data = api(
            f"fixtures?id={fixture_id}"
        )

        response = match_data.get("response", [])

        if not response:

            return jsonify(
                ok=False,
                erreur="Match introuvable."
            ), 404

        match = response[0]

        fixture = match.get("fixture", {})
        teams = match.get("teams", {})
        league = match.get("league", {})
        goals = match.get("goals", {})

        home = teams.get("home", {}) or {}
        away = teams.get("away", {}) or {}

        home_id = home.get("id")
        away_id = away.get("id")

        league_id = league.get("id")
        season = league.get("season")


        # ----------------------------------------------------
        # CLASSEMENT
        # ----------------------------------------------------

        standings = get_standings(
            league_id,
            season
        )

        home_row = find_team_row(
            standings,
            home_id
        )

        away_row = find_team_row(
            standings,
            away_id
        )


        # ----------------------------------------------------
        # FORME
        # ----------------------------------------------------

        home_form = get_last_matches(
            home_id
        )

        away_form = get_last_matches(
            away_id
        )


        # ----------------------------------------------------
        # H2H
        # ----------------------------------------------------

        h2h = get_h2h(
            home_id,
            away_id
        )


        # ----------------------------------------------------
        # STATISTIQUES DU MATCH
        # ----------------------------------------------------

        home_stats = team_statistics(
            int(fixture_id),
            home_id
        )

        away_stats = team_statistics(
            int(fixture_id),
            away_id
        )


        # ----------------------------------------------------
        # BUTS ATTENDUS
        # ----------------------------------------------------

        home_lambda, away_lambda = expected_goals(
            home_row,
            away_row
        )


        # ----------------------------------------------------
        # PROBABILITÉS 1X2 + SCORES
        # ----------------------------------------------------

        p1 = 0.0
        px = 0.0
        p2 = 0.0

        scores = []

        for h in range(0, 8):

            for a in range(0, 8):

                probability = (
                    poisson(h, home_lambda)
                    * poisson(a, away_lambda)
                )

                scores.append(
                    (
                        probability,
                        h,
                        a
                    )
                )

                if h > a:
                    p1 += probability

                elif h == a:
                    px += probability

                else:
                    p2 += probability


        total = p1 + px + p2

        if total <= 0:
            total = 1


        scores.sort(
            key=lambda x: x[0],
            reverse=True
        )


        # ----------------------------------------------------
        # OVER / UNDER
        # ----------------------------------------------------

        over_1_5 = 0
        over_2_5 = 0
        over_3_5 = 0

        btts_yes = 0

        for probability, h, a in scores:

            total_goals = h + a

            if total_goals >= 2:
                over_1_5 += probability

            if total_goals >= 3:
                over_2_5 += probability

            if total_goals >= 4:
                over_3_5 += probability

            if h >= 1 and a >= 1:
                btts_yes += probability


        # ----------------------------------------------------
        # PRÉDICTION FINALE
        # ----------------------------------------------------

        if p1 >= px and p1 >= p2:

            final_prediction = (
                f"Victoire {home.get('name')}"
            )

        elif p2 >= p1 and p2 >= px:

            final_prediction = (
                f"Victoire {away.get('name')}"
            )

        else:

            final_prediction = "Match nul"


        # ----------------------------------------------------
        # RÉSULTAT FINAL
        # ----------------------------------------------------

        return jsonify(

            ok=True,

            fixture_id=int(fixture_id),

            match={

                "domicile": home.get("name"),

                "domicile_id": home_id,

                "domicile_logo": home.get("logo"),

                "exterieur": away.get("name"),

                "exterieur_id": away_id,

                "exterieur_logo": away.get("logo"),

                "championnat": league.get("name"),

                "pays": league.get("country"),

                "league_id": league_id,

                "season": season,

                "date": fixture.get("date"),

                "statut": (
                    fixture.get("status", {})
                    or {}
                ).get("long")
            },


            # ------------------------------------------------
            # 1X2
            # ------------------------------------------------

            "1x2": {

                "domicile": percentage(
                    p1,
                    total
                ),

                "nul": percentage(
                    px,
                    total
                ),

                "exterieur": percentage(
                    p2,
                    total
                )
            },


            # ------------------------------------------------
            # FORM
            # ------------------------------------------------

            "forme": {

                "domicile": (
                    home_row.get("form")
                    or None
                ),

                "exterieur": (
                    away_row.get("form")
                    or None
                ),

                "domicile_5_derniers": home_form,

                "exterieur_5_derniers": away_form
            },


            # ------------------------------------------------
            # CLASSEMENT
            # ------------------------------------------------

            "classement": {

                "domicile": home_row.get("rank"),

                "exterieur": away_row.get("rank"),

                "domicile_points": home_row.get("points"),

                "exterieur_points": away_row.get("points"),

                "domicile_joues": (
                    home_row.get("all", {})
                    or {}
                ).get("played"),

                "exterieur_joues": (
                    away_row.get("all", {})
                    or {}
                ).get("played")
            },


            # ------------------------------------------------
            # BUTS
            # ------------------------------------------------

            "buts": {

                "attendus_domicile": round(
                    home_lambda,
                    2
                ),

                "attendus_exterieur": round(
                    away_lambda,
                    2
                ),

           
