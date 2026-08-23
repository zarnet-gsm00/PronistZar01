import math
import json
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_DIR, ".env"))
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(PROJECT_DIR, "score_pro.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class MatchAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    league_id = db.Column(db.String(20), nullable=False)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    data_source = db.Column(db.String(120), nullable=False)
    xg_home = db.Column(db.Float, nullable=False)
    xg_away = db.Column(db.Float, nullable=False)
    gf_home = db.Column(db.Float, nullable=False)
    gf_away = db.Column(db.Float, nullable=False)
    corners_home = db.Column(db.Float, nullable=False)
    corners_away = db.Column(db.Float, nullable=False)
    shots_home = db.Column(db.Float, nullable=False)
    shots_away = db.Column(db.Float, nullable=False)
    poss_home = db.Column(db.Float, nullable=False)
    poss_away = db.Column(db.Float, nullable=False)
    home_win_pct = db.Column(db.Float, nullable=False)
    draw_pct = db.Column(db.Float, nullable=False)
    away_win_pct = db.Column(db.Float, nullable=False)
    exact_score = db.Column(db.String(20), nullable=False)
    confidence = db.Column(db.String(20), nullable=True)
    explanation = db.Column(db.Text, nullable=True)
    market_summary = db.Column(db.Text, nullable=True)
    data_warnings = db.Column(db.Text, nullable=True)
    actual_score = db.Column(db.String(20), nullable=True)
    evaluation = db.Column(db.String(20), nullable=True)


class TeamProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.String(20), nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    venue = db.Column(db.String(10), nullable=False)
    metrics_json = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("league_id", "team_name", "venue", name="uq_team_profile"),)


with app.app_context():
    db.create_all()
    existing_columns = {column[1] for column in db.session.execute(db.text("PRAGMA table_info(match_analysis)"))}
    for column_name, column_type in {
        "confidence": "VARCHAR(20)",
        "explanation": "TEXT",
        "market_summary": "TEXT",
        "data_warnings": "TEXT"
        ,"actual_score": "VARCHAR(20)",
        "evaluation": "VARCHAR(20)"
    }.items():
        if column_name not in existing_columns:
            db.session.execute(db.text(f"ALTER TABLE match_analysis ADD COLUMN {column_name} {column_type}"))
    db.session.commit()

# Ligas ampliadas con Perú, EE.UU., Holanda, Argentina y Brasil
LEAGUES = {
    "39": "Premier League",
    "140": "La Liga",
    "135": "Serie A",
    "78": "Bundesliga",
    "61": "Ligue 1",
    "128": "Liga 1-Perú",
    "253": "MLS",
    "88": "Eredivisie",
    "128_arg": "LigaArgentina",
    "71": "Brasileirão Serie A"
}



# Base de datos simulada de equipos por ID de liga para que el desplegable funcione de inmediato
TEAMS_BY_LEAGUE = {
    "39": ["Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Chelsea", "Crystal Palace", "Everton", "Fulham", "Liverpool", "Manchester City", "Manchester United", "Newcastle", "Nottingham Forest", "Tottenham", "West Ham", "Wolves"],
    "140": ["Alavés", "Athletic Club", "Atlético de Madrid", "Barcelona", "Celta de Vigo", "Getafe", "Girona", "Las Palmas", "Mallorca", "Osasuna", "Rayo Vallecano", "Real Betis", "Real Madrid", "Real Sociedad", "Sevilla", "Valencia", "Villarreal"],
    "135": ["AC Milan", "Atalanta", "Bologna", "Cagliari", "Fiorentina", "Genoa", "Inter de Milán", "Juventus", "Lazio", "Lecce", "Monza", "Nápoles", "Parma", "Roma", "Torino", "Udinese", "Venecia"],
    "78": ["Augsburgo", "Bayer Leverkusen", "Bayern de Múnich", "Borussia Dortmund", "Borussia Mönchengladbach", "Eintracht Frankfurt", "Friburgo", "Hoffenheim", "Mainz 05", "RB Leipzig", "St. Pauli", "Stuttgart", "Union Berlin", "Werder Bremen", "Wolfsburgo"],
    "61": ["AS Monaco", "Auxerre", "Estrasburgo", "Le Havre", "Lens", "Lille", "Lyon", "Marsella", "Montpellier", "Nantes", "Niza", "París Saint-Germain", "Rennes", "Saint-Étienne", "Toulouse"],
    "128": ["Alianza Lima", "ADT", "Comerciantes Unidos", "Cienciano", "Cusco FC", "Deportivo Garcilaso", "FBC Melgar", "Sport Huancayo", "Sporting Cristal", "UTC", "Universitario de Deportes"],
    "253": ["Atlanta United", "Austin FC", "Charlotte FC", "Columbus Crew", "FC Cincinnati", "Inter Miami", "LA Galaxy", "Los Angeles FC", "Minnesota United", "New York City FC", "New York Red Bulls", "Orlando City", "Portland Timbers", "Seattle Sounders", "Toronto FC"],
    "88": ["Ajax", "AZ Alkmaar", "Feyenoord", "Fortuna Sittard", "Go Ahead Eagles", "Groningen", "Heerenveen", "NEC Nijmegen", "PSV Eindhoven", "Sparta Rotterdam", "Twente", "Utrecht", "Vitesse"],
    "128_arg": ["Argentinos Juniors", "Boca Juniors", "Estudiantes", "Gimnasia y Esgrima", "Huracán", "Independiente", "Lanús", "Newell's Old Boys", "Racing Club", "River Plate", "Rosario Central", "San Lorenzo", "Talleres", "Vélez Sarsfield"],
    "71": ["Athletico Paranaense", "Atlético Mineiro", "Bahia", "Botafogo", "Bragantino", "Corinthians", "Cruzeiro", "Flamengo", "Fluminense", "Fortaleza", "Gremio", "Internacional", "Palmeiras", "Santos", "São Paulo", "Vasco da Gama"]
}

API_LEAGUE_IDS = {
    "39": "39",
    "140": "140",
    "135": "135",
    "78": "78",
    "61": "61",
    "128": "281",
    "253": "253",
    "88": "88",
    "128_arg": "128",
    "71": "71"
}

DEFAULT_METRICS = {
    "attacks_h": 0.0, "attacks_a": 0.0,
    "goals_against_h": 1.1, "goals_against_a": 1.4,
    "home_goals_h": 2.0, "home_goals_a": 0.0,
    "away_goals_h": 0.0, "away_goals_a": 1.2,
    "corners_h": 5.5, "corners_a": 4.2,
    "shots_h": 14.0, "shots_a": 11.0,
    "clean_sheets_h": 0, "clean_sheets_a": 0,
    "poss_h": 55.0, "poss_a": 45.0,
    "league_matches_h": 0, "league_matches_a": 0,
    "pitch_h": "", "pitch_a": "", "star_player_h": "", "star_player_a": "",
    "rest_days_h": 0, "rest_days_a": 0,
    "accurate_passes_h": 0, "accurate_passes_a": 0,
    "form_last6_h": "", "form_last6_a": "",
    "avg_goals_h": 1.8, "avg_goals_a": 1.3,
    "data_source": "Valores manuales"
}


def _average_value(value, default, venue=None):
    if isinstance(value, dict):
        if venue in value:
            value = value[venue]
        else:
            value = value.get("average")
    if isinstance(value, str):
        value = value.replace("%", "").strip()
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _non_negative_value(value, default):
    parsed_value = _average_value(value, default)
    if parsed_value is None:
        return default
    return max(0.0, parsed_value)


def fetch_team_metrics(team_name, league_id, venue):
    api_key = os.getenv("API_FOOTBALL_KEY")
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        api_key = rapidapi_key
    if not api_key:
        return None

    season = os.getenv("FOOTBALL_SEASON", "2025")
    api_league_id = API_LEAGUE_IDS.get(league_id, league_id)
    if rapidapi_key and not os.getenv("API_FOOTBALL_KEY"):
        base_url = "https://api-football-v1.p.rapidapi.com/v3"
        headers = {
            "x-rapidapi-key": rapidapi_key,
            "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
        }
    else:
        base_url = "https://v3.football.api-sports.io"
        headers = {"x-apisports-key": api_key}

    try:
        team_response = requests.get(
            f"{base_url}/teams",
            params={"name": team_name, "league": api_league_id, "season": season},
            headers=headers,
            timeout=8
        )
        team_response.raise_for_status()
        team_data = team_response.json().get("response", [])
        if not team_data:
            return None

        team_id = team_data[0]["team"]["id"]
        stats_response = requests.get(
            f"{base_url}/teams/statistics",
            params={"league": api_league_id, "season": season, "team": team_id},
            headers=headers,
            timeout=8
        )
        stats_response.raise_for_status()
        stats = stats_response.json().get("response", {})
        goals_average = _average_value(
            stats.get("goals", {}).get("for"), 0, venue
        )
        shots = stats.get("shots", {})
        fouls = stats.get("fouls", {})
        cards = stats.get("cards", {})
        offsides = stats.get("offsides")
        penalties = stats.get("penalty", {}).get("scored")
        return {
            "goals_against": _average_value(stats.get("goals", {}).get("against"), 0, venue),
            "corners": _average_value(
                stats.get("corner", stats.get("corners", {})).get("for"),
                0,
                venue
            ),
            "shots": _average_value(stats.get("shots", {}).get("on"), 0, venue),
            "poss": _average_value(stats.get("possession"), 0, venue),
            "clean_sheets": _average_value(stats.get("clean_sheet", {}).get("total"), 0),
            "league_matches": _average_value(stats.get("fixtures", {}).get("played", {}).get("total"), 0),
            "accurate_passes": _average_value(stats.get("passes", {}).get("accuracy"), 0, venue),
            "avg_goals": goals_average
        }
    except (KeyError, requests.RequestException, ValueError):
        return None


def get_metrics(home_team, away_team, league_id):
    home_api_metrics = fetch_team_metrics(home_team, league_id, "home")
    away_api_metrics = fetch_team_metrics(away_team, league_id, "away")
    metrics = DEFAULT_METRICS.copy()

    if home_api_metrics:
        metrics.update({
            "goals_against_h": home_api_metrics["goals_against"],
            "corners_h": home_api_metrics["corners"],
            "shots_h": home_api_metrics["shots"], "poss_h": home_api_metrics["poss"],
            "clean_sheets_h": home_api_metrics["clean_sheets"],
            "league_matches_h": home_api_metrics["league_matches"],
            "accurate_passes_h": home_api_metrics["accurate_passes"],
            "avg_goals_h": home_api_metrics["avg_goals"]
        })
    if away_api_metrics:
        metrics.update({
            "goals_against_a": away_api_metrics["goals_against"],
            "corners_a": away_api_metrics["corners"],
            "shots_a": away_api_metrics["shots"], "poss_a": away_api_metrics["poss"],
            "clean_sheets_a": away_api_metrics["clean_sheets"],
            "league_matches_a": away_api_metrics["league_matches"],
            "accurate_passes_a": away_api_metrics["accurate_passes"],
            "avg_goals_a": away_api_metrics["avg_goals"]
        })

    if home_api_metrics and away_api_metrics:
        metrics["data_source"] = "API-Football: local/visitante"
    elif home_api_metrics or away_api_metrics:
        metrics["data_source"] = "API-Football parcial + valores de respaldo"
    else:
        metrics["data_source"] = "Valores de respaldo: API sin datos"
    return metrics

def poisson_probability(lam, k):
    return (math.e ** (-lam) * (lam ** k)) / math.factorial(k)

def _form_factor(form):
    outcomes = [item.strip().upper() for item in str(form or "").replace(",", "-").split("-") if item.strip()]
    if not outcomes:
        return 1.0
    points = sum({"G": 1.0, "E": 0.45, "P": 0.0}.get(item, 0.5) for item in outcomes[-6:])
    return 0.88 + (points / min(len(outcomes), 6)) * 0.24

def _positive_factor(value, baseline, weight, minimum=0.0):
    if value is None or value <= minimum:
        return 1.0
    return 1.0 + ((value - baseline) / baseline) * weight

def calculate_expected_goals(metrics):
    home_attack = (metrics["avg_goals_h"] * 0.55 + metrics["home_goals_h"] * 0.30 + metrics["avg_goals_h"] * 0.15)
    away_attack = (metrics["avg_goals_a"] * 0.55 + metrics["away_goals_a"] * 0.30 + metrics["avg_goals_a"] * 0.15)
    home_defense = metrics["goals_against_a"]
    away_defense = metrics["goals_against_h"]

    expected_home = (home_attack * 0.62) + (home_defense * 0.38)
    expected_away = (away_attack * 0.62) + (away_defense * 0.38)
    home_factor = (
        _positive_factor(metrics["corners_h"], 5.0, 0.04)
        * _positive_factor(metrics["shots_h"], 12.0, 0.06)
        * _positive_factor(metrics["poss_h"], 50.0, 0.04)
        * _positive_factor(metrics["accurate_passes_h"], 80.0, 0.03)
        * _positive_factor(metrics["attacks_h"], 100.0, 0.04)
        * _positive_factor(metrics["rest_days_h"], 5.0, 0.025)
        * _form_factor(metrics["form_last6_h"])
    )
    away_factor = (
        _positive_factor(metrics["corners_a"], 5.0, 0.04)
        * _positive_factor(metrics["shots_a"], 12.0, 0.06)
        * _positive_factor(metrics["poss_a"], 50.0, 0.04)
        * _positive_factor(metrics["accurate_passes_a"], 80.0, 0.03)
        * _positive_factor(metrics["attacks_a"], 100.0, 0.04)
        * _positive_factor(metrics["rest_days_a"], 5.0, 0.025)
        * _form_factor(metrics["form_last6_a"])
    )
    home_clean_sheet_factor = 1.0
    away_clean_sheet_factor = 1.0
    if metrics["league_matches_h"] > 0:
        home_clean_sheet_factor -= min(metrics["clean_sheets_h"] / metrics["league_matches_h"], 0.5) * 0.12
    if metrics["league_matches_a"] > 0:
        away_clean_sheet_factor -= min(metrics["clean_sheets_a"] / metrics["league_matches_a"], 0.5) * 0.12
    expected_home *= away_clean_sheet_factor
    expected_away *= home_clean_sheet_factor
    return max(0.15, min(expected_home * home_factor, 5.0)), max(0.15, min(expected_away * away_factor, 5.0))

def calculate_match_probabilities(xg_home, xg_away):
    max_goals = 6
    home_win, draw, away_win = 0.0, 0.0, 0.0
    most_likely_score = (0, 0)
    max_prob = 0.0

    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p_home = poisson_probability(xg_home, h)
            p_away = poisson_probability(xg_away, a)
            prob = p_home * p_away
            
            if h > a:
                home_win += prob
            elif h == a:
                draw += prob
            else:
                away_win += prob
                
            if prob > max_prob:
                max_prob = prob
                most_likely_score = (h, a)

    return {
        "home_win_pct": round(home_win * 100, 1),
        "draw_pct": round(draw * 100, 1),
        "away_win_pct": round(away_win * 100, 1),
        "exact_score": f"{most_likely_score[0]} - {most_likely_score[1]}"
    }


def probability_over(line, expected_value):
    threshold = math.floor(line)
    probability_under_or_equal = sum(
        poisson_probability(expected_value, goals)
        for goals in range(threshold + 1)
    )
    return round((1 - probability_under_or_equal) * 100, 1)


def probability_both_score(expected_home, expected_away):
    home_zero = poisson_probability(expected_home, 0)
    away_zero = poisson_probability(expected_away, 0)
    return round((1 - home_zero) * (1 - away_zero) * 100, 1)


def period_result_probabilities(expected_home, expected_away):
    probabilities = calculate_match_probabilities(expected_home, expected_away)
    return {
        "home": probabilities["home_win_pct"],
        "draw": probabilities["draw_pct"],
        "away": probabilities["away_win_pct"]
    }


def calculate_market_probabilities(metrics, expected_home, expected_away):
    total_goals = expected_home + expected_away
    total_corners = metrics["corners_h"] + metrics["corners_a"]
    total_shots = metrics["shots_h"] + metrics["shots_a"]
    first_half_goals = total_goals * 0.44
    second_half_goals = total_goals * 0.56
    first_half_home = expected_home * 0.44
    first_half_away = expected_away * 0.44
    second_half_home = expected_home * 0.56
    second_half_away = expected_away * 0.56
    first_result = period_result_probabilities(first_half_home, first_half_away)
    second_result = period_result_probabilities(second_half_home, second_half_away)
    return {
        "over_25_goals": probability_over(2.5, total_goals),
        "over_15_goals": probability_over(1.5, total_goals),
        "under_35_goals": round(100 - probability_over(3.5, total_goals), 1),
        "both_score": probability_both_score(expected_home, expected_away),
        "home_over_05": probability_over(0.5, expected_home),
        "away_over_05": probability_over(0.5, expected_away),
        "over_95_corners": probability_over(9.5, total_corners),
        "over_85_corners": probability_over(8.5, total_corners),
        "over_105_corners": probability_over(10.5, total_corners),
        "over_115_corners": probability_over(11.5, total_corners),
        "over_95_shots": probability_over(9.5, total_shots),
        "over_215_shots": probability_over(21.5, total_shots),
        "home_over_55_shots": probability_over(5.5, metrics["shots_h"]),
        "away_over_55_shots": probability_over(5.5, metrics["shots_a"]),
        "first_half_over_05": probability_over(0.5, first_half_goals),
        "second_half_over_05": probability_over(0.5, second_half_goals),
        "first_half_home": first_result["home"], "first_half_draw": first_result["draw"], "first_half_away": first_result["away"],
        "second_half_home": second_result["home"], "second_half_draw": second_result["draw"], "second_half_away": second_result["away"],
        "first_half_expected": round(first_half_goals, 2),
        "second_half_expected": round(second_half_goals, 2),
        "total_corners": round(total_corners, 1),
        "total_shots": round(total_shots, 1)
    }


def assess_data_quality(metrics):
    numeric_fields = (
        "attacks_h", "attacks_a", "goals_against_h", "goals_against_a", "home_goals_h",
        "away_goals_a", "corners_h", "corners_a", "shots_h", "shots_a", "poss_h", "poss_a",
        "league_matches_h", "league_matches_a", "rest_days_h", "rest_days_a",
        "accurate_passes_h", "accurate_passes_a", "avg_goals_h", "avg_goals_a"
    )
    missing = metrics.get("missing_fields", [field for field in numeric_fields if metrics.get(field) in (None, 0)])
    warnings = []
    if missing:
        warnings.append(f"No se completaron: {', '.join(missing)}.")
    possession_total = metrics["poss_h"] + metrics["poss_a"]
    if possession_total and abs(possession_total - 100) > 5:
        warnings.append(f"La posesión suma {possession_total:g}%, revisa los datos.")
    completeness = max(0.0, 1 - (len(missing) / len(numeric_fields)))
    if completeness >= 0.9 and not warnings:
        confidence = "Alta"
    elif completeness >= 0.65:
        confidence = "Media"
    else:
        confidence = "Baja"
    return confidence, warnings


def build_analysis_explanation(metrics, results, confidence, warnings):
    explanation = (
        f"El modelo estima {results['expected_goals_home']:.2f} goles para el local y "
        f"{results['expected_goals_away']:.2f} para el visitante. Combina ataque, defensa, "
        "localía, ataques, remates, córneres, posesión, pases, descanso, porterías a cero y racha."
    )
    if warnings:
        explanation += " Revisa: " + " ".join(warnings)
    return explanation


def save_match_analysis(league_id, home_team, away_team, metrics, results):
    analysis = MatchAnalysis(
        league_id=league_id,
        home_team=home_team,
        away_team=away_team,
        data_source=metrics["data_source"],
        xg_home=results["expected_goals_home"], xg_away=results["expected_goals_away"],
        gf_home=metrics["avg_goals_h"], gf_away=metrics["avg_goals_a"],
        corners_home=metrics["corners_h"], corners_away=metrics["corners_a"],
        shots_home=metrics["shots_h"], shots_away=metrics["shots_a"],
        poss_home=metrics["poss_h"], poss_away=metrics["poss_a"],
        home_win_pct=results["home_win_pct"],
        draw_pct=results["draw_pct"],
        away_win_pct=results["away_win_pct"],
        exact_score=results["exact_score"]
        ,confidence=results["confidence"], explanation=results["explanation"],
        market_summary=json.dumps(calculate_market_probabilities(metrics, results["expected_goals_home"], results["expected_goals_away"])),
        data_warnings=json.dumps(results["data_warnings"])
    )
    try:
        db.session.add(analysis)
        db.session.commit()
    except Exception:
        db.session.rollback()


PROFILE_METRICS = (
    "attacks", "goals_against", "home_goals", "away_goals", "corners", "shots",
    "clean_sheets", "poss", "league_matches", "pitch", "star_player", "rest_days",
    "accurate_passes", "form_last6", "avg_goals"
)


def save_team_profile(league_id, team_name, venue, metrics):
    values = {
        metric: metrics.get(f"{metric}_{'h' if venue == 'home' else 'a'}")
        for metric in PROFILE_METRICS
    }
    profile = TeamProfile.query.filter_by(
        league_id=league_id, team_name=team_name, venue=venue
    ).first()
    if profile is None:
        profile = TeamProfile(
            league_id=league_id, team_name=team_name, venue=venue,
            metrics_json=json.dumps(values)
        )
        db.session.add(profile)
    else:
        profile.metrics_json = json.dumps(values)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_team_profile(league_id, team_name, venue):
    profile = TeamProfile.query.filter_by(
        league_id=league_id, team_name=team_name, venue=venue
    ).first()
    if profile is None:
        return None


@app.template_filter("from_json")
def from_json_filter(value):
    try:
        return json.loads(value) if value else {}
    except (TypeError, ValueError):
        return {}
    try:
        return json.loads(profile.metrics_json)
    except (TypeError, ValueError):
        return None


def get_recent_analyses():
    return MatchAnalysis.query.order_by(MatchAnalysis.created_at.desc()).limit(10).all()


@app.route('/history/delete', methods=['POST'])
def delete_history():
    try:
        MatchAnalysis.query.delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(url_for('index') + '#history')


@app.route('/history/evaluate/<int:analysis_id>', methods=['POST'])
def evaluate_analysis(analysis_id):
    analysis = db.session.get(MatchAnalysis, analysis_id)
    actual_score = request.form.get('actual_score', '').strip()
    if analysis is not None and actual_score:
        try:
            actual_home, actual_away = (int(value.strip()) for value in actual_score.split('-', 1))
            predicted_home, predicted_away = (int(value.strip()) for value in analysis.exact_score.split('-', 1))
            analysis.actual_score = f"{actual_home} - {actual_away}"
            analysis.evaluation = "Acierto" if (actual_home > actual_away) == (predicted_home > predicted_away) and (actual_home == actual_away) == (predicted_home == predicted_away) else "Fallo"
            db.session.commit()
        except (ValueError, TypeError):
            db.session.rollback()
    return redirect(url_for('index') + '#history')


@app.route('/history/delete/<int:analysis_id>', methods=['POST'])
def delete_single_analysis(analysis_id):
    analysis = db.session.get(MatchAnalysis, analysis_id)
    if analysis is not None:
        try:
            db.session.delete(analysis)
            db.session.commit()
        except Exception:
            db.session.rollback()
    return redirect(url_for('index') + '#history')

# Ruta API para devolver los equipos según la liga seleccionada
@app.route('/api/get-teams', methods=['GET'])
def get_teams():
    league_id = request.args.get('league_id', '39')
    teams = TEAMS_BY_LEAGUE.get(league_id, ["Equipo A", "Equipo B"])
    return jsonify({"teams": teams})


@app.route('/api/get-team-profile', methods=['GET'])
def get_team_profile_api():
    league_id = request.args.get('league_id', '39')
    team_name = request.args.get('team_name', '')
    venue = request.args.get('venue', 'home')
    if venue not in ('home', 'away') or not team_name:
        return jsonify({"metrics": None})
    return jsonify({"metrics": get_team_profile(league_id, team_name, venue)})

@app.route('/', methods=['GET', 'POST'])
def index():
    selected_league = request.form.get('league', '39')
    current_teams = TEAMS_BY_LEAGUE.get(selected_league, TEAMS_BY_LEAGUE['39'])
    
    if request.method == 'POST':
        home_team = request.form.get('home_team')
        away_team = request.form.get('away_team')

        metrics = get_metrics(home_team, away_team, selected_league)
        posted_metric_fields = {
            f"{metric}_{suffix}": f"{metric}_{venue}"
            for metric in PROFILE_METRICS
            for suffix, venue in (("h", "home"), ("a", "away"))
            if not ((metric == "home_goals" and suffix == "a") or (metric == "away_goals" and suffix == "h"))
        }
        missing_fields = []
        for metric_name, form_name in posted_metric_fields.items():
            value = request.form.get(form_name, "").strip()
            metric_key = metric_name.rsplit("_", 1)[0]
            if not value:
                if metric_key not in ("pitch", "star_player", "form_last6"):
                    missing_fields.append(metric_name)
                    metrics[metric_name] = DEFAULT_METRICS.get(metric_name, metrics[metric_name])
                else:
                    metrics[metric_name] = ""
            elif metric_key in ("pitch", "star_player", "form_last6"):
                metrics[metric_name] = value
            else:
                metrics[metric_name] = _non_negative_value(value, metrics[metric_name])
        metrics["missing_fields"] = missing_fields
        
        expected_home, expected_away = calculate_expected_goals(metrics)
        results = calculate_match_probabilities(expected_home, expected_away)
        results["expected_goals_home"] = round(expected_home, 2)
        results["expected_goals_away"] = round(expected_away, 2)
        results.update(calculate_market_probabilities(metrics, expected_home, expected_away))
        confidence, warnings = assess_data_quality(metrics)
        results["confidence"] = confidence
        results["data_warnings"] = warnings
        results["explanation"] = build_analysis_explanation(metrics, results, confidence, warnings)
        save_match_analysis(selected_league, home_team, away_team, metrics, results)
        save_team_profile(selected_league, home_team, "home", metrics)
        save_team_profile(selected_league, away_team, "away", metrics)
        return render_template('index.html', leagues=LEAGUES, selected_league=selected_league, teams=current_teams, home=home_team, away=away_team, m=metrics, results=results, history=get_recent_analyses())
                               
    default_metrics = DEFAULT_METRICS.copy()
    default_metrics["data_source"] = "Valores de respaldo: aún no se ha consultado la API"
    default_home_goals, default_away_goals = calculate_expected_goals(default_metrics)
    default_results = {"home_win_pct": 52.3, "draw_pct": 24.1, "away_win_pct": 23.6, "exact_score": "2 - 1"}
    default_results.update({"expected_goals_home": round(default_home_goals, 2), "expected_goals_away": round(default_away_goals, 2)})
    default_results.update(calculate_market_probabilities(default_metrics, default_home_goals, default_away_goals))
    default_confidence, default_warnings = assess_data_quality(default_metrics)
    default_results["confidence"] = default_confidence
    default_results["data_warnings"] = default_warnings
    default_results["explanation"] = build_analysis_explanation(default_metrics, default_results, default_confidence, default_warnings)
    return render_template('index.html', leagues=LEAGUES, selected_league=selected_league, teams=current_teams, home=current_teams[0], away=current_teams[1], m=default_metrics, results=default_results, history=get_recent_analyses())

if __name__ == '__main__':
    app.run(debug=True)