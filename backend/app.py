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
# JMK PREDICTION FOOT
# Backend Flask + API-Football
# ============================================================

app = Flask(
    __name__,
    static_folder="../frontend",
    static_url_path=""
)

CORS(app)


# ============================================================
# CONFIGURATION
# ============================================================

API = "https://v3.football.api-sports.io"

TOKEN = (
    os.getenv("API_FOOTBALL_KEY")
    or os.getenv("SPORTMONKS_TOKEN")
    or ""
).strip()


# ============================================================
# OUTILS
# ============================================================

def api(path):
    if not TOKEN:
        raise RuntimeError(
            "API_FOOTBALL_KEY non configurée sur PythonAnywhere."
        )

    response = requests.get(
        API + "/" + path,
        headers={
            "x-apisports-key": TOKEN
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(str(data["errors"]))

    return data


def safe_api(path):
    try:
        return api(path)
    except Exception:
        return {}


def poisson(k, lam):
    if lam <= 0:
        return 0.0

    return (
        math.exp(-lam)
        * (lam ** k)
        / math.factorial(k)
    )


def percentage(value, total):
    if not total:
        return None

    return round(
        (value / total) * 100,
        1
    )


# ============================================================
# STATUT DU SERVEUR
# ============================================================

@app.get("/api/status")
def status():

    return jsonify(
        ok=True,
        app="JMK Prediction Foot",
        service="API-Football",
        tokenConfigured=bool(TOKEN),
        version="2.1.0"
    )


# ============================================================
# MATCHS DU JOUR / DEMAIN
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
            f"fixtures?date={date}"
            f"&timezone=Europe/Paris"
        )

        matches = []

        for item in data.get("response", []):

            fixture = item.get(
                "fixture",
                {}
            )

            teams = item.get(
                "teams",
                {}
            )

            league = item.get(
                "league",
                {}
            )

            status_data = fixture.get(
                "status",
                {}
            ) or {}

            home = teams.get(
                "home",
                {}
            ) or {}

            away = teams.get(
                "away",
                {}
            ) or {}

            matches.append({

                "fixture_id":
                    fixture.get("id"),

                "date_utc":
                    fixture.get("date"),

                "horaire":
                    (fixture.get("date") or "")[11:16],

                "pays":
                    league.get("country"),

                "championnat":
                    league.get("name"),

                "league_id":
                    league.get("id"),

                "season":
                    league.get("season"),

                "round":
                    league.get("round"),

                "statut":
                    status_data.get("long"),

                "code_statut":
                    status_data.get("short"),

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
# EXTRACTION DES STATISTIQUES
# ============================================================

def get_stat(statistics, *names):

    wanted = {
        str(name).lower()
        for name in names
    }

    for item in statistics or []:

        stat_name = str(
            item.get("type", "")
        ).lower()

        if stat_name in wanted:

            value = item.get("value")

            if isinstance(value, str):

                value = (
                    value
                    .replace("%", "")
                    .strip()
                )

            return value

    return None


# ============================================================
# STATISTIQUES DU MATCH
# ============================================================

def get_fixture_statistics(
    fixture_id,
    home_id,
    away_id
):

    data = safe_api(
        f"fixtures/statistics?fixture={fixture_id}"
    )

    statistics_by_team = {}

    for team_data in data.get(
        "response",
        []
    ):

        team_id = (
            team_data
            .get("team", {})
            .get("id")
        )

        statistics_by_team[
            team_id
        ] = team_data.get(
            "statistics",
            []
        )

    def extract(team_id):

        stats = statistics_by_team.get(
            team_id,
            []
        )

        return {

            "possession":
                get_stat(
                    stats,
                    "Ball Possession"
                ),

            "tirs":
                get_stat(
                    stats,
                    "Total Shots"
                ),

            "tirs_cadres":
                get_stat(
                    stats,
                    "Shots on Goal",
                    "Shots on Target"
                ),

            "tirs_non_cadres":
                get_stat(
                    stats,
                    "Shots off Goal"
                ),

            "tirs_bloques":
                get_stat(
                    stats,
                    "Blocked Shots"
                ),

            "corners":
                get_stat(
                    stats,
                    "Corner Kicks"
                ),

            "fautes":
                get_stat(
                    stats,
                    "Fouls"
                ),

            "cartons_jaunes":
                get_stat(
                    stats,
                    "Yellow Cards"
                ),

            "cartons_rouges":
                get_stat(
                    stats,
                    "Red Cards"
                ),

            "hors_jeu":
                get_stat(
                    stats,
                    "Offsides"
                )
        }

    return (
        extract(home_id),
        extract(away_id)
    )


# ============================================================
# CLASSEMENT
# ============================================================

def get_standings(
    league_id,
    season
):

    if not league_id or not season:
        return []

    data = safe_api(
        f"standings?league={league_id}"
        f"&season={season}"
    )

    response = data.get(
        "response",
        []
    )

    if not response:
        return []

    standings = (
        response[0]
        .get("league", {})
        .get("standings", [])
    )

    if (
        standings
        and isinstance(standings[0], list)
    ):

        return standings[0]

    return standings


def find_team_row(
    rows,
    team_id
):

    for row in rows:

        if (
            row
            .get("team", {})
            .get("id")
            == team_id
        ):

            return row

    return {}


# ============================================================
# 5 DERNIERS MATCHS
# ============================================================

def get_last_matches(team_id):

    data = safe_api(
        f"fixtures?team={team_id}"
        f"&last=5"
        f"&timezone=Europe/Paris"
    )

    results = []

    for item in data.get(
        "response",
        []
    ):

        fixture = item.get(
            "fixture",
            {}
        )

        teams = item.get(
            "teams",
            {}
        )

        goals = item.get(
            "goals",
            {}
        )

        home = teams.get(
            "home",
            {}
        ) or {}

        away = teams.get(
            "away",
            {}
        ) or {}

        home_goals = goals.get(
            "home"
        )

        away_goals = goals.get(
            "away"
        )

        result = None

        if (
            home_goals is not None
            and away_goals is not None
        ):

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

            "fixture_id":
                fixture.get("id"),

            "date":
                fixture.get("date"),

            "adversaire":
                (
                    away.get("name")
                    if team_id == home.get("id")
                    else home.get("name")
                ),

            "domicile":
                home.get("name"),

            "exterieur":
                away.get("name"),

            "score":
                (
                    f"{home_goals}-{away_goals}"
                    if (
                        home_goals is not None
                        and away_goals is not None
                    )
                    else None
                ),

            "resultat":
                result

        })

    return results[:5]


# ============================================================
# H2H
# ============================================================

def get_h2h(
    home_id,
    away_id
):

    data = safe_api(
        f"fixtures/headtohead"
        f"?h2h={home_id}-{away_id}"
        f"&last=10"
    )

    results = []

    for item in data.get(
        "response",
        []
    ):

        fixture = item.get(
            "fixture",
            {}
        )

        teams = item.get(
            "teams",
            {}
        )

        goals = item.get(
            "goals",
            {}
        )

        home = teams.get(
            "home",
            {}
        ) or {}

        away = teams.get(
            "away",
            {}
        ) or {}

        results.append({

            "fixture_id":
                fixture.get("id"),

            "date":
                fixture.get("date"),

            "domicile":
                home.get("name"),

            "exterieur":
                away.get("name"),

            "score":
                (
                    f"{goals.get('home')}"
                    f"-{goals.get('away')}"
                    if (
                        goals.get("home") is not None
                        and goals.get("away") is not None
                    )
                    else None
                )
        })

    return results
    # ============================================================
# CALCUL DES BUTS ATTENDUS
# ============================================================

def expected_goals(home_row, away_row):

    def goals_for(row):

        all_data = row.get("all", {}) or {}

        played = all_data.get("played") or 0

        goals = all_data.get(
            "goals",
            {}
        ) or {}

        scored = goals.get("for") or 0

        if played <= 0:
            return 1.20

        return scored / played


    def goals_against(row):

        all_data = row.get("all", {}) or {}

        played = all_data.get("played") or 0

        goals = all_data.get(
            "goals",
            {}
        ) or {}

        conceded = goals.get("against") or 0

        if played <= 0:
            return 1.20

        return conceded / played


    home_attack = goals_for(
        home_row
    )

    home_defence = goals_against(
        home_row
    )

    away_attack = goals_for(
        away_row
    )

    away_defence = goals_against(
        away_row
    )


    home_lambda = max(
        0.15,
        (
            home_attack
            + away_defence
        ) / 2
    )


    away_lambda = max(
        0.15,
        (
            away_attack
            + home_defence
        ) / 2
    )


    return (
        home_lambda,
        away_lambda
    )


# ============================================================
# ANALYSE D'UN MATCH
# ============================================================

@app.get("/api/analyze")
def analyze():

    fixture_id = (
        request.args
        .get("fixture", "")
        .strip()
    )


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
        # RÉCUPÉRER LE MATCH
        # ----------------------------------------------------

        data = api(
            f"fixtures?id={fixture_id}"
        )


        response = data.get(
            "response",
            []
        )


        if not response:

            return jsonify(
                ok=False,
                erreur="Match introuvable."
            ), 404


        match = response[0]


        fixture = match.get(
            "fixture",
            {}
        )


        teams = match.get(
            "teams",
            {}
        )


        league = match.get(
            "league",
            {}
        )


        home = teams.get(
            "home",
            {}
        ) or {}


        away = teams.get(
            "away",
            {}
        ) or {}


        home_id = home.get(
            "id"
        )


        away_id = away.get(
            "id"
        )


        league_id = league.get(
            "id"
        )


        season = league.get(
            "season"
        )


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
        # STATISTIQUES
        # ----------------------------------------------------

        home_stats, away_stats = (
            get_fixture_statistics(
                int(fixture_id),
                home_id,
                away_id
            )
        )


        # ----------------------------------------------------
        # BUTS ATTENDUS
        # ----------------------------------------------------

        home_lambda, away_lambda = (
            expected_goals(
                home_row,
                away_row
            )
        )


        # ----------------------------------------------------
        # PROBABILITÉS
        # ----------------------------------------------------

        p1 = 0.0

        px = 0.0

        p2 = 0.0


        scores = []


        over_1_5 = 0.0

        over_2_5 = 0.0

        over_3_5 = 0.0

        btts_yes = 0.0


        # ----------------------------------------------------
        # MATRICE DES SCORES 0 À 8
        # ----------------------------------------------------

        for home_goals in range(9):

            for away_goals in range(9):

                probability = (

                    poisson(
                        home_goals,
                        home_lambda
                    )

                    *

                    poisson(
                        away_goals,
                        away_lambda
                    )

                )


                scores.append({

                    "score": (
                        f"{home_goals}"
                        f"-"
                        f"{away_goals}"
                    ),

                    "probability":
                        probability

                })


                if home_goals > away_goals:

                    p1 += probability


                elif home_goals == away_goals:

                    px += probability


                else:

                    p2 += probability


                total_goals = (
                    home_goals
                    + away_goals
                )


                if total_goals >= 2:

                    over_1_5 += probability


                if total_goals >= 3:

                    over_2_5 += probability


                if total_goals >= 4:

                    over_3_5 += probability


                if (
                    home_goals >= 1
                    and away_goals >= 1
                ):

                    btts_yes += probability


        total_probability = (
            p1
            + px
            + p2
        )


        if total_probability <= 0:

            total_probability = 1.0


        # ----------------------------------------------------
        # TOP 5 SCORES
        # ----------------------------------------------------

        scores.sort(
            key=lambda x:
                x["probability"],
            reverse=True
        )


        exact_scores = []


        for item in scores[:5]:

            exact_scores.append({

                "score":
                    item["score"],

                "probabilite":
                    round(
                        item["probability"]
                        * 100,
                        1
                    )

            })


        # ----------------------------------------------------
        # PRÉDICTION 1X2
        # ----------------------------------------------------

        home_probability = (
            p1
            / total_probability
            * 100
        )


        draw_probability = (
            px
            / total_probability
            * 100
        )


        away_probability = (
            p2
            / total_probability
            * 100
        )


        # ----------------------------------------------------
        # PRÉDICTION FINALE
        # ----------------------------------------------------

        if (
            home_probability
            >= draw_probability
            and
            home_probability
            >= away_probability
        ):

            final_prediction = (
                f"Victoire "
                f"{home.get('name')}"
            )


        elif (
            away_probability
            >= home_probability
            and
            away_probability
            >= draw_probability
        ):

            final_prediction = (
                f"Victoire "
                f"{away.get('name')}"
            )


        else:

            final_prediction = (
                "Match nul"
            )


        # ----------------------------------------------------
        # RÉSULTAT JSON
        # ----------------------------------------------------

        return jsonify(

            ok=True,


            fixture_id=int(
                fixture_id
            ),


            match={

                "domicile":
                    home.get("name"),

                "domicile_id":
                    home_id,

                "domicile_logo":
                    home.get("logo"),

                "exterieur":
                    away.get("name"),

                "exterieur_id":
                    away_id,

                "exterieur_logo":
                    away.get("logo"),

                "championnat":
                    league.get("name"),

                "pays":
                    league.get("country"),

                "league_id":
                    league_id,

                "season":
                    season,

                "date":
                    fixture.get("date"),

                "statut":
                    (
                        fixture
                        .get("status", {})
                        or {}
                    ).get("long")

            },


            # ------------------------------------------------
            # PRÉDICTION FINALE
            # ------------------------------------------------

            prediction=final_prediction,

            final_prediction=final_prediction,


            # ------------------------------------------------
            # 1X2
            # ------------------------------------------------

            **{

                "1x2": {

                    "domicile":
                        round(
                            home_probability,
                            1
                        ),

                    "nul":
                        round(
                            draw_probability,
                            1
                        ),

                    "exterieur":
                        round(
                            away_probability,
                            1
                        )

                },


                # --------------------------------------------
                # FORME
                # --------------------------------------------

                "forme": {

                    "domicile":
                        home_row.get(
                            "form"
                        ),

                    "exterieur":
                        away_row.get(
                            "form"
                        ),

                    "domicile_5_derniers":
                        home_form,

                    "exterieur_5_derniers":
                        away_form

                },


                # --------------------------------------------
                # CLASSEMENT
                # --------------------------------------------

                "classement": {

                    "domicile":
                        home_row.get(
                            "rank"
                        ),

                    "exterieur":
                        away_row.get(
                            "rank"
                        ),

                    "domicile_points":
                        home_row.get(
                            "points"
                        ),

                    "exterieur_points":
                        away_row.get(
                            "points"
                        )

                },


                # --------------------------------------------
                # BUTS
                # --------------------------------------------

                "buts": {

                    "attendus_domicile":
                        round(
                            home_lambda,
                            2
                        ),

                    "attendus_exterieur":
                        round(
                            away_lambda,
                            2
                        ),

                    "marques_domicile":
                        (
                            home_row
                            .get("all", {})
                            .get("goals", {})
                            .get("for")
                        ),

                    "marques_exterieur":
                        (
                            away_row
                            .get("all", {})
                            .get("goals", {})
                            .get("for")
                        ),

                    "encaisses_domicile":
                        (
                            home_row
                            .get("all", {})
                            .get("goals", {})
                            .get("against")
                        ),

                    "encaisses_exterieur":
                        (
                            away_row
                            .get("all", {})
                            .get("goals", {})
                            .get("against")
                        )

                },


                # --------------------------------------------
                # BTTS
                # --------------------------------------------

                "btts": {

                    "oui":
                        round(
                            btts_yes
                            * 100,
                            1
                        ),

                    "non":
                        round(
                            (1 - btts_yes)
                            * 100,
                            1
                        )

                },


                # --------------------------------------------
                # OVER / UNDER
                # --------------------------------------------

                "over_under": {

                    "over_1_5":
                        round(
                            over_1_5
                            * 100,
                            1
                        ),

                    "under_1_5":
                        round(
                            (1 - over_1_5)
                            * 100,
                            1
                        ),

                    "over_2_5":
                        round(
                            over_2_5
                            * 100,
                            1
                        ),

                    "under_2_5":
                        round(
                            (1 - over_2_5)
                            * 100,
                            1
                        ),

                    "over_3_5":
                        round(
                            over_3_5
                            * 100,
                            1
                        ),

                    "under_3_5":
                        round(
                            (1 - over_3_5)
                            * 100,
                            1
                        )

                },


                # --------------------------------------------
                # STATISTIQUES
                # --------------------------------------------

                "statistiques": {

                    "domicile":
                        home_stats,

                    "exterieur":
                        away_stats

                },


                # --------------------------------------------
                # H2H
                # --------------------------------------------

                "h2h":
                    h2h,


                # --------------------------------------------
                # 5 SCORES EXACTS
                # --------------------------------------------

                "exact_scores":
                    exact_scores

            }

        )


    except Exception as e:

        return jsonify(
            ok=False,
            erreur=str(e)
        ), 502


# ============================================================
# PAGE PRINCIPALE
# ============================================================

@app.get("/")
def index():

    index_file = os.path.join(
        FRONTEND_DIR,
        "index.html"
    )


    if os.path.exists(
        index_file
    ):

        return send_from_directory(
            FRONTEND_DIR,
            "index.html"
        )


    return jsonify(
        ok=True,
        app="JMK Prediction Foot",
        message="Backend actif"
    )


# ============================================================
# LANCEMENT LOCAL
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "5000"
            )
        )
    )


                    

    
        
        


            
    

        
                
            
                
