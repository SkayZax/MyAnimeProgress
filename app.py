from deep_translator import GoogleTranslator
from flask import Flask, abort, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from api.API import API, APIError
from securite import Limiteur, mot_de_passe_trop_courant
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask_wtf.csrf import CSRFError, CSRFProtect
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
import hashlib
import os
import re
import secrets
import threading
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from itsdangerous import BadSignature, URLSafeTimedSerializer
import requests
from urllib.parse import urlparse

# Chargement variables d'environnement depuis un fichier .env (si présent)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

app = Flask(__name__)
# En dev local (python app.py), on n'est généralement pas derrière un reverse proxy.
# ProxyFix peut casser les URLs si aucun header X-Forwarded-* n'est fourni.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
api = API()
# CONFIGURATION INDISPENSABLE
# Signe les sessions : à définir dans .env, jamais dans le code (dépôt public).
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    app.logger.warning("SECRET_KEY absente de .env : clé temporaire, les sessions seront perdues au redémarrage.")
    app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # Crée un fichier database.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Si ton app est réellement montée sous un sous-chemin (ex: /MyAnimeProgress) via un reverse proxy,
# il faut configurer ça côté serveur/proxy. En dev local, ce réglage casse souvent les liens.
# app.config['APPLICATION_ROOT'] = '/MyAnimeProgress'

# Assure que les cookies de session sont valables à la racine
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# À mettre à 1 en production (HTTPS) : le cookie ne circule alors jamais en clair.
app.config['SESSION_COOKIE_SECURE'] = os.getenv('COOKIE_SECURE', '0') == '1'
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
app.config['WTF_CSRF_TIME_LIMIT'] = None  # le jeton dure autant que la session

csrf = CSRFProtect(app)
limiteur = Limiteur()
MINUTE, HEURE = 60, 3600
JOUR = 24 * HEURE
ID_MAX = 2**31 - 1  # au-delà, SQLite refuse la valeur
SUIVIS_MAX = 500  # animés par compte

db = SQLAlchemy(app)

# --- Email ---
# On garde Flask-Mail importé pour éviter de casser l'app si vous aviez du code/templating,
# mais l'envoi de la vérification passe désormais par Brevo (API HTTP).

# Variables attendues (dans .env):
#   BREVO_API_KEY=...
#   BREVO_FROM_EMAIL=no-reply@votre-domaine
#   BREVO_FROM_NAME=MyAnimeProgress
# Optionnel:
#   BREVO_TEMPLATE_ID=123 (si vous utilisez un template Brevo)
#   BREVO_TIMEOUT=10

mail = Mail(app)

# Gestion de la connexion
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None


ADULT_GENRES = {"Ecchi", "Erotica", "Hentai"}


@app.errorhandler(APIError)
def api_unavailable(error):
    """Affiche une page claire quand l'API d'animés ne répond pas."""
    app.logger.warning("API d'animés indisponible : %s", error)
    return render_template("api_error.html"), 503


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(CSRFError)
def csrf_invalid(error):
    flash("La page avait expiré. Recommence.", "error")
    return redirect(_safe_referrer())


@app.before_request
def limit_requests():
    """Évite qu'un visiteur n'épuise le quota de l'API d'animés."""
    if request.endpoint != 'static' and not limiteur.autoriser(f"page:{request.remote_addr}", 120, MINUTE):
        return _too_many()


@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
        "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    )
    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000')
    return response


def _too_many():
    return render_template("429.html"), 429


def _safe_referrer() -> str:
    return request.referrer if _is_safe_url(request.referrer) else url_for("index")


def _is_safe_url(target: str) -> bool:
    """Empêche les redirections ouvertes (open redirect)."""
    # Les navigateurs lisent \ comme / et ignorent les caractères de contrôle
    if not target or "\\" in target or any(ord(c) < 32 or ord(c) == 127 for c in target):
        return False
    try:
        url = urlparse(target)
    except ValueError:
        return False
    if url.scheme or url.netloc:
        # Adresse complète (Referer) : même site exactement. "http:///x" n'a pas de netloc, donc refusé.
        return url.scheme in ("http", "https") and url.netloc == request.host
    return target.startswith("/") and not target.startswith("//")


def _duration_minutes(anime: dict) -> int:
    """Durée d'un épisode à partir de "23 min per ep" ; 24 min si inconnue."""
    trouve = re.search(r"(\d+) min", (anime.get("duration") or "").lower())
    return int(trouve.group(1)) if trouve and int(trouve.group(1)) > 0 else 24


def _save_info(anime: dict):
    """Enregistre les infos d'un animé renvoyé par l'API."""
    info = db.session.get(AnimeInfo, anime["mal_id"]) or AnimeInfo(id=anime["mal_id"])
    info.title = (anime.get("title") or "?")[:300]
    info.image = ((anime.get("images") or {}).get("jpg") or {}).get("large_image_url") or ""
    info.duration_min = _duration_minutes(anime)
    info.episodes = anime.get("episodes") or None
    info.airing = bool(anime.get("airing"))
    info.released = api.get_released_episodes(info.id) if info.airing and not info.episodes else None
    info.updated_at = datetime.utcnow()
    db.session.add(info)
    db.session.commit()
    return info


APPELS_PAR_PAGE = 10


def _infos(ids) -> dict:
    """Infos des animés demandés. Rafraîchit au plus APPELS_PAR_PAGE fiches absentes ou anciennes."""
    infos = {}
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 500):
        for info in AnimeInfo.query.filter(AnimeInfo.id.in_(ids[i:i + 500])):
            infos[info.id] = info
    maintenant = datetime.utcnow()

    def perimee(info):
        return info.updated_at < maintenant - (timedelta(hours=6) if info.airing else timedelta(days=14))

    a_lire = [i for i in ids if i not in infos] + [i for i in ids if i in infos and perimee(infos[i])]
    for anime_id in a_lire[:APPELS_PAR_PAGE]:
        try:
            anime = api.get_animes(anime_id).get("data")
            if anime:
                infos[anime_id] = _save_info(anime)
        except APIError as e:
            app.logger.warning("Infos non rafraîchies : %s", e)
            break  # API en panne : on affiche ce qu'on a déjà
        except IntegrityError:
            db.session.rollback()  # enregistré au même instant par une autre requête
    return infos


def _entry_view(entry, info) -> dict:
    """Ce que les pages Progression et Favoris affichent pour un animé suivi."""
    total = (info.episodes if info else None) or entry.total_episode or None
    released = info.released if info and not total else None
    if released:
        # La liste de l'API peut avoir du retard : un épisode vu est forcément sorti.
        released = max(released, entry.current_episode or 0)
    vus = int(entry.current_episode or 0)
    duree = info.duration_min if info else 24
    return {
        'id': entry.anime_id,
        'title': info.title if info else f"Animé n° {entry.anime_id}",
        'image': info.image if info else "",
        'current_episode': entry.current_episode,
        'total_episode': total,
        'released': released,
        'duration_min': duree,
        'watched_minutes': vus * duree,
    }


def _list_is_full(anime_id: int) -> bool:
    suivis = Useranime.query.filter_by(user_id=current_user.id)
    return suivis.count() >= SUIVIS_MAX and suivis.filter_by(anime_id=anime_id).first() is None


def _age_verified() -> bool:
    return bool(session.get("age_verified", False))


def _anime_is_adult(anime: dict) -> bool:
    """Détecte un contenu adulte via rating/genres (Tenrai)."""
    if not anime:
        return False
    rating = (anime.get("rating") or "").lower()
    if rating.startswith("rx"):
        return True
    genres = anime.get("genres") or []
    for g in genres:
        name = (g.get("name") or "").strip()
        if name in ADULT_GENRES:
            return True
    return False


@app.route("/age-gate", methods=["GET", "POST"])
def age_gate():
    next_url = request.args.get("next") or request.form.get("next") or url_for("index")
    if not _is_safe_url(next_url):
        next_url = url_for("index")

    if request.method == "POST":
        if request.form.get("confirm") == "yes":
            session["age_verified"] = True
            # Optionnel: expiration “souple” (en jours). Ici on laisse la session gérer.
            return redirect(next_url)
        flash("Accès au contenu adulte refusé.", "warning")
        return redirect(url_for("index"))

    return render_template("age_gate.html", next_url=next_url)


@app.route("/age-gate/revoke", methods=["POST"])
def revoke_age_gate():
    session.pop("age_verified", None)
    flash("Le contenu adulte est de nouveau masqué.", "info")
    return redirect(_safe_referrer())

@login_manager.user_loader
def load_user(user_id):
    """Compte connecté, si sa session existe toujours côté serveur."""
    jeton = session.get('sid')
    if not jeton:
        return None
    ouverte = db.session.get(OpenSession, _hash_token(jeton))
    if not ouverte or str(ouverte.user_id) != str(user_id) \
            or ouverte.created_at < datetime.utcnow() - timedelta(days=SESSION_JOURS):
        return None
    return db.session.get(User, ouverte.user_id)


SESSION_JOURS = 30
SESSIONS_MAX = 10  # appareils connectés par compte


def _hash_token(jeton: str) -> str:
    # La base ne contient que l'empreinte : la lire ne permet pas de se connecter
    return hashlib.sha256(jeton.encode()).hexdigest()


def _open_session(user) -> None:
    """Connecte l'utilisateur avec une session neuve, révocable à la déconnexion."""
    adulte = _age_verified()
    session.clear()
    if adulte:
        session['age_verified'] = True
    jeton = secrets.token_urlsafe(32)
    session['sid'] = jeton
    maintenant = datetime.utcnow()
    OpenSession.query.filter(OpenSession.created_at < maintenant - timedelta(days=SESSION_JOURS)).delete()
    anciennes = OpenSession.query.filter_by(user_id=user.id).order_by(OpenSession.created_at.desc()).offset(SESSIONS_MAX - 1).all()
    for ancienne in anciennes:
        db.session.delete(ancienne)
    db.session.add(OpenSession(id=_hash_token(jeton), user_id=user.id, created_at=maintenant))
    db.session.commit()
    login_user(user)


@app.route("/", methods=["GET"])
def index():
    page = request.args.get('page', 1, type=int)
    genre_name = request.args.get('genres', type=str)
    search_query = request.args.get('search', type=str)

    # Nettoyage des champs (évite les recherches " " et valeurs None)
    if genre_name:
        genre_name = genre_name.strip()
    if search_query:
        search_query = search_query.strip()

    title = "MyAnimeProgress"

    # Par défaut, on masque le contenu adulte tant que l'âge n'est pas confirmé.
    if genre_name in ADULT_GENRES and not _age_verified():
        flash("Ce genre contient du contenu adulte. Confirme que tu as 18+ pour continuer.", "warning")
        return redirect(url_for("age_gate", next=request.full_path))

    # IMPORTANT: logique exclusive.
    # Priorité à la recherche, sinon filtre genre, sinon liste par défaut.
    if search_query:
        animes = api.search_anime(search_query, page)
        title = f"Résultats pour : {search_query}"
    elif genre_name == 'Action':
        animes = api.get_animes_by_genre(genre_id=1, page=page)
    elif genre_name == 'Adventure':
        animes = api.get_animes_by_genre(genre_id=2, page=page)
    elif genre_name == 'Racing':
        animes = api.get_animes_by_genre(genre_id=3, page=page)
    elif genre_name == 'Comedy':
        animes = api.get_animes_by_genre(genre_id=4, page=page)
    elif genre_name == 'Avant Garde':
        animes = api.get_animes_by_genre(genre_id=5, page=page)
    elif genre_name == 'Mythology':
        animes = api.get_animes_by_genre(genre_id=6, page=page)
    elif genre_name == 'Mystery':
        animes = api.get_animes_by_genre(genre_id=7, page=page)
    elif genre_name == 'Drama':
        animes = api.get_animes_by_genre(genre_id=8, page=page)
    elif genre_name == 'Ecchi':
        animes = api.get_animes_by_genre(genre_id=9, page=page)
    elif genre_name == 'Fantasy':
        animes = api.get_animes_by_genre(genre_id=10, page=page)
    elif genre_name == 'Strategy Game':
        animes = api.get_animes_by_genre(genre_id=11, page=page)
    elif genre_name == 'Hentai':
        animes = api.get_animes_by_genre(genre_id=12, page=page)
    elif genre_name == 'Historical':
        animes = api.get_animes_by_genre(genre_id=13, page=page)
    elif genre_name == 'Horror':
        animes = api.get_animes_by_genre(genre_id=14, page=page)
    elif genre_name == 'Kids':
        animes = api.get_animes_by_genre(genre_id=15, page=page)
    elif genre_name == 'Martial Arts':
        animes = api.get_animes_by_genre(genre_id=17, page=page)
    elif genre_name == 'Mecha':
        animes = api.get_animes_by_genre(genre_id=18, page=page)
    elif genre_name == 'Music':
        animes = api.get_animes_by_genre(genre_id=19, page=page)
    elif genre_name == 'Parody':
        animes = api.get_animes_by_genre(genre_id=20, page=page)
    elif genre_name == 'Samurai':
        animes = api.get_animes_by_genre(genre_id=21, page=page)
    elif genre_name == 'Romance':
        animes = api.get_animes_by_genre(genre_id=22, page=page)
    elif genre_name == 'School':
        animes = api.get_animes_by_genre(genre_id=23, page=page)
    elif genre_name == 'Sci-Fi':
        animes = api.get_animes_by_genre(genre_id=24, page=page)
    elif genre_name == 'Shoujo':
        animes = api.get_animes_by_genre(genre_id=25, page=page)
    elif genre_name == 'Girls Love':
        animes = api.get_animes_by_genre(genre_id=26, page=page)
    elif genre_name == 'Shounen':
        animes = api.get_animes_by_genre(genre_id=27, page=page)
    elif genre_name == 'Boys Love':
        animes = api.get_animes_by_genre(genre_id=28, page=page)
    elif genre_name == 'Space':
        animes = api.get_animes_by_genre(genre_id=29, page=page)
    elif genre_name == 'Sports':
        animes = api.get_animes_by_genre(genre_id=30, page=page)
    elif genre_name == 'Super Power':
        animes = api.get_animes_by_genre(genre_id=31, page=page)
    elif genre_name == 'Vampire':
        animes = api.get_animes_by_genre(genre_id=32, page=page)
    elif genre_name == 'Harem':
        animes = api.get_animes_by_genre(genre_id=35, page=page)
    elif genre_name == 'Slice of Life':
        animes = api.get_animes_by_genre(genre_id=36, page=page)
    elif genre_name == 'Supernatural':
        animes = api.get_animes_by_genre(genre_id=37, page=page)
    elif genre_name == 'Military':
        animes = api.get_animes_by_genre(genre_id=38, page=page)
    elif genre_name == 'Police':
        animes = api.get_animes_by_genre(genre_id=39, page=page)
    elif genre_name == 'Psychological':
        animes = api.get_animes_by_genre(genre_id=40, page=page)
    elif genre_name == 'Suspense':
        animes = api.get_animes_by_genre(genre_id=41, page=page)
    elif genre_name == 'Seinen':
        animes = api.get_animes_by_genre(genre_id=42, page=page)
    elif genre_name == 'Josei':
        animes = api.get_animes_by_genre(genre_id=43, page=page)
    elif genre_name == 'Award Winning':
        animes = api.get_animes_by_genre(genre_id=46, page=page)
    elif genre_name == 'Gourmet':
        animes = api.get_animes_by_genre(genre_id=47, page=page)
    elif genre_name == 'Work Life':
        animes = api.get_animes_by_genre(genre_id=48, page=page)
    elif genre_name == 'Erotica':
        animes = api.get_animes_by_genre(genre_id=49, page=page)

    else:
        animes = api.get_animepage(page)

    recus = len(animes)
    if not _age_verified():
        animes = [a for a in animes if not _anime_is_adult(a)]

    return render_template(
        "index.html",
        animes=animes,
        masques=recus - len(animes),
        page_pleine=recus > 0,
        current_page=page,
        title=title,
        age_verified=_age_verified(),
        adult_genres=sorted(ADULT_GENRES),
    )
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_code = db.Column(db.String(6), nullable=True)
    verification_expires_at = db.Column(db.DateTime, nullable=True)
    # Change à chaque inscription : lie le code à la personne qui a choisi le mot de passe
    verification_nonce = db.Column(db.String(32), nullable=True)
    # Mot de passe oublié : code envoyé par email, lié à la session qui l'a demandé
    reset_code = db.Column(db.String(6), nullable=True)
    reset_expires_at = db.Column(db.DateTime, nullable=True)
    reset_nonce = db.Column(db.String(32), nullable=True)


class OpenSession(db.Model):
    id = db.Column(db.String(64), primary_key=True)  # empreinte du jeton
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False)


class AnimeInfo(db.Model):
    """Infos d'un animé gardées en base : évite un appel API par animé suivi."""
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)  # identifiant MyAnimeList
    title = db.Column(db.String(300), nullable=False)
    image = db.Column(db.String(300), nullable=False)
    duration_min = db.Column(db.Integer, nullable=False)
    episodes = db.Column(db.Integer, nullable=True)
    airing = db.Column(db.Boolean, nullable=False, default=False)
    released = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False)


def _generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


_EMAILS = {
    'verification': {
        'sujet': 'Votre code de vérification MyAnimeProgress',
        'titre': 'Vérifie ton compte',
        'intro': 'Voici ton code de vérification',
        'texte': 'Votre code de vérification MyAnimeProgress est',
    },
    'reset': {
        'sujet': 'Réinitialisation de votre mot de passe MyAnimeProgress',
        'titre': 'Change ton mot de passe',
        'intro': 'Voici ton code pour choisir un nouveau mot de passe',
        'texte': 'Votre code de réinitialisation MyAnimeProgress est',
    },
}


def _send_verification_email(to_email: str, code: str, motif: str = 'verification') -> None:
    """Envoie un email de vérification via Brevo (Sendinblue) API.

    Configuration via variables d'environnement:
      - BREVO_API_KEY (obligatoire)
      - BREVO_FROM_EMAIL (obligatoire)
      - BREVO_FROM_NAME (optionnel)
      - BREVO_TEMPLATE_ID (optionnel, sinon email texte simple)

    Doc: https://developers.brevo.com/docs/send-a-transactional-email
    """

    api_key = os.getenv('BREVO_API_KEY')
    from_email = os.getenv('BREVO_FROM_EMAIL')
    from_name = os.getenv('BREVO_FROM_NAME', 'MyAnimeProgress')
    template_id = os.getenv('BREVO_TEMPLATE_ID')
    timeout_s = float(os.getenv('BREVO_TIMEOUT', '10'))

    if not api_key or not from_email:
        raise RuntimeError("Brevo non configuré (BREVO_API_KEY/BREVO_FROM_EMAIL).")

    url = 'https://api.brevo.com/v3/smtp/email'
    headers = {
        'accept': 'application/json',
        'api-key': api_key,
        'content-type': 'application/json',
    }

    textes = _EMAILS[motif]

    # Petit template HTML “propre” (sans images externes obligatoires), compatible clients mail.
    html_content = f"""\
<!doctype html>
<html lang=\"fr\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>{textes['sujet']}</title>
  </head>
  <body style=\"margin:0;padding:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#111827;\">
    <div style=\"max-width:560px;margin:0 auto;padding:24px;\">
      <div style=\"background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;\">
        <div style=\"background:linear-gradient(90deg,#1f2937,#111827);padding:18px 20px;\">
          <div style=\"font-size:16px;font-weight:700;color:#ffffff;letter-spacing:.2px;\">MyAnimeProgress</div>
        </div>

        <div style=\"padding:22px 20px 10px 20px;\">
          <h1 style=\"margin:0 0 12px 0;font-size:18px;line-height:1.35;\">{textes['titre']}</h1>
          <p style=\"margin:0 0 14px 0;font-size:14px;line-height:1.6;color:#374151;\">
            {textes['intro']} (valide <strong>15 minutes</strong>) :
          </p>

          <div style=\"text-align:center;margin:18px 0 16px 0;\">
            <div style=\"display:inline-block;background:#f3f4f6;border:1px dashed #d1d5db;border-radius:12px;\
                        padding:14px 18px;font-size:26px;font-weight:800;letter-spacing:6px;color:#111827;\">{code}</div>
          </div>

          <p style=\"margin:0 0 10px 0;font-size:13px;line-height:1.6;color:#6b7280;\">
            Si tu n'es pas à l'origine de cette demande, tu peux ignorer cet email.
          </p>
        </div>

        <div style=\"padding:14px 20px 18px 20px;border-top:1px solid #e5e7eb;background:#fafafa;\">
          <p style=\"margin:0;font-size:12px;line-height:1.5;color:#9ca3af;\">
            © {datetime.utcnow().year} MyAnimeProgress — Email automatique, merci de ne pas répondre.
          </p>
        </div>
      </div>
    </div>
  </body>
</html>
"""

    text_content = (
        f"{textes['texte']} : {code}\n\n"
        "Ce code expire dans 15 minutes.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email."
    )

    if template_id:
        payload = {
            'to': [{'email': to_email}],
            'templateId': int(template_id),
            'params': {
                'CODE': code,
                'code': code,
                'APP_NAME': 'MyAnimeProgress',
                'HTML': html_content,
            },
        }
    else:
        payload = {
            'sender': {'email': from_email, 'name': from_name},
            'to': [{'email': to_email}],
            'subject': textes['sujet'],
            'textContent': text_content,
            'htmlContent': html_content,
        }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    if resp.status_code >= 400:
        raise RuntimeError(f"Erreur Brevo HTTP {resp.status_code}: {resp.text}")


def _dev_should_show_code() -> bool:
    return os.getenv('DEV_SHOW_VERIFICATION_CODE', '0') in {'1', 'true', 'True', 'yes', 'YES'}

class Useranime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    anime_id = db.Column(db.Integer, nullable=False)
    current_episode = db.Column(db.Integer, default=0)
    total_episode = db.Column(db.Integer, nullable=True)
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    # Révoque la session côté serveur : un cookie copié avant ne marche plus
    OpenSession.query.filter_by(id=_hash_token(session.get('sid', ''))).delete()
    db.session.commit()
    logout_user()

    # Nettoie la session pour éviter tout état résiduel
    session.clear()

    # Expire explicitement le cookie "remember" si jamais il est utilisé
    resp = redirect(url_for('index'))
    resp.delete_cookie('remember_token')
    return resp


@app.route('/favorites')
@login_required
def favorites():
    entries = Useranime.query.filter_by(user_id=current_user.id, is_favorite=True).all()
    infos = _infos(e.anime_id for e in entries)
    return render_template('favorites.html', animes=[_entry_view(e, infos.get(e.anime_id)) for e in entries])


@app.route('/toggle_favorite', methods=['POST'])
@login_required
def toggle_favorite():
    anime_id = request.form.get('anime_id', type=int)
    total_ep = request.form.get('total_episode', type=int)
    if not anime_id or not 1 <= anime_id <= ID_MAX or not 0 <= (total_ep or 0) <= 100_000:
        return redirect(url_for('index'))

    if _list_is_full(anime_id):
        flash(f"Ta liste est pleine ({SUIVIS_MAX} animés).", "error")
        return redirect(_safe_referrer())

    entry = Useranime.query.filter_by(user_id=current_user.id, anime_id=anime_id).first()
    if entry is None:
        entry = Useranime(
            user_id=current_user.id,
            anime_id=anime_id,
            current_episode=0,
            total_episode=total_ep,
            is_favorite=True,
        )
        db.session.add(entry)
    else:
        entry.is_favorite = not bool(entry.is_favorite)
        if total_ep and (entry.total_episode is None or entry.total_episode == 0):
            entry.total_episode = total_ep

    db.session.commit()

    # Retour à la page précédente si possible
    return redirect(_safe_referrer())

# Sert à passer le même temps à vérifier un compte inexistant (ne révèle pas qui est inscrit)
_FAUX_HACHAGE = generate_password_hash(secrets.token_hex(16), method='pbkdf2:sha256')
MDP_MIN, MDP_MAX = 8, 128


def _normalize_email(value) -> str:
    return (value or '').strip().lower()


def _find_user(email: str):
    return User.query.filter(db.func.lower(User.email) == email).first() if email else None


COOKIE_APPAREIL = 'appareil'


def _device_signer():
    return URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='appareil-connu')


def _known_device(user):
    """Identifiant de l'appareil s'il s'est déjà connecté à ce compte, sinon None."""
    try:
        user_id, appareil = _device_signer().loads(request.cookies.get(COOKIE_APPAREIL, ''), max_age=180 * JOUR)
        return appareil if user and user_id == user.id else None
    except (BadSignature, TypeError, ValueError):
        return None


def _remember_device(response, user):
    response.set_cookie(
        COOKIE_APPAREIL,
        _device_signer().dumps([user.id, secrets.token_hex(8)]),
        max_age=180 * JOUR, httponly=True, samesite='Lax', secure=app.config['SESSION_COOKIE_SECURE'],
    )
    return response


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = _normalize_email(request.form.get('email'))
        password = request.form.get('password') or ''

        # Échecs par IP, par IP et compte, puis par compte (attaque répartie) ou par appareil connu
        ip = request.remote_addr
        user = _find_user(email)
        appareil = _known_device(user)
        limites = (
            (f"login:ip:{ip}", 20, 15 * MINUTE),
            (f"login:ip-compte:{ip}:{email}", 8, 15 * MINUTE),
            # Un appareil déjà connecté garde son propre compteur : personne ne peut le bloquer à distance
            (f"login:appareil:{appareil}", 8, 15 * MINUTE) if appareil else (f"login:compte:{email}", 50, HEURE),
        )
        if any(limiteur.trop(*limite) for limite in limites):
            return _too_many()

        valide = len(password) <= MDP_MAX and check_password_hash(user.password if user else _FAUX_HACHAGE, password)
        if user and valide:
            limiteur.oublier(limites[1][0])
            if not user.is_verified:
                _start_verification(user)
                flash("Votre compte n'est pas vérifié. Entrez le code reçu par email.", "error")
                return redirect(url_for('verify'))
            _open_session(user)
            return _remember_device(redirect(url_for('index')), user)

        for cle, _, fenetre in limites:
            limiteur.compter(cle, fenetre)
        flash("Email ou mot de passe incorrect.", "error")
        return redirect(url_for('login'))

    return render_template('login.html')


def _registration_error(username: str, email: str, password: str):
    if not 3 <= len(username) <= 30:
        return "Le nom d'utilisateur doit faire entre 3 et 30 caractères."
    if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return "L'adresse email n'est pas valide."
    if not MDP_MIN <= len(password) <= MDP_MAX:
        return f"Le mot de passe doit faire au moins {MDP_MIN} caractères."
    if mot_de_passe_trop_courant(password, username, email):
        return "Ce mot de passe est trop facile à deviner. Choisis-en un autre."
    # Un compte jamais vérifié ne réserve ni l'email ni le pseudo de quelqu'un d'autre
    existant = _find_user(email)
    if existant and existant.is_verified:
        return "Cet email est déjà utilisé."
    homonyme = User.query.filter(db.func.lower(User.username) == username.lower()).first()
    if homonyme and homonyme != existant:
        return "Ce nom d'utilisateur est déjà pris. Veuillez en choisir un autre."
    return None


def _send_code(user, sent_message: str) -> None:
    """Envoie le code et informe l'utilisateur, sans montrer les détails techniques."""
    try:
        _send_verification_email(user.email, user.verification_code)
        flash(sent_message, "success")
    except Exception as e:
        app.logger.error("Envoi du code impossible : %s", e)
        msg = "L'email n'a pas pu être envoyé. Réessaie plus tard."
        if _dev_should_show_code():
            msg += f" (Code DEV: {user.verification_code})"
        flash(msg, "error")


def _start_verification(user) -> None:
    """Autorise cette session, et elle seule, à vérifier le compte."""
    session['verify'] = [user.id, user.verification_nonce or '']


def _purge_unverified() -> None:
    """Supprime les inscriptions jamais vérifiées, un jour après l'expiration de leur code."""
    limite = datetime.utcnow() - timedelta(days=1)
    User.query.filter(User.is_verified.is_(False), User.verification_expires_at < limite).delete()
    db.session.commit()


def _new_code(user) -> None:
    user.verification_code = _generate_verification_code()
    user.verification_expires_at = datetime.utcnow() + timedelta(minutes=15)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == "POST":
        if not limiteur.autoriser(f"register:{request.remote_addr}", 15, HEURE):
            return _too_many()

        username = (request.form.get("username") or '').strip()
        email = _normalize_email(request.form.get("email"))
        password = request.form.get("password") or ''

        _purge_unverified()
        erreur = _registration_error(username, email, password)
        if erreur:
            flash(erreur, "error")
            return render_template('register.html')

        # Nouvel utilisateur (non vérifié), ou reprise d'une inscription jamais vérifiée.
        # Le nonce change : une inscription précédente avec cet email ne peut plus être validée.
        new_user = _find_user(email) or User(email=email)
        new_user.username = username
        new_user.password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user.is_verified = False
        new_user.verification_nonce = secrets.token_hex(16)
        _new_code(new_user)
        db.session.add(new_user)
        try:
            db.session.commit()
        except IntegrityError:
            # Deux inscriptions identiques au même instant
            db.session.rollback()
            flash("Cet email ou ce nom d'utilisateur est déjà utilisé.", "error")
            return render_template('register.html')

        limiteur.oublier(f"code:essai:{new_user.id}")
        _start_verification(new_user)
        # Compté par email : on ne peut pas inonder quelqu'un en s'inscrivant en boucle à sa place
        if not limiteur.autoriser(f"code:envoi:{email}", 4, HEURE):
            flash("Trop de codes demandés pour cet email. Réessaie dans une heure.", "error")
            return redirect(url_for('verify'))
        _send_code(new_user, "Compte créé. Le code t'a été envoyé par email.")
        return redirect(url_for('verify'))

    return render_template('register.html')


def _user_to_verify():
    """Compte en attente, connu seulement de celui qui vient de s'inscrire ou de donner son mot de passe."""
    user_id, nonce = session.get('verify') or (None, None)
    user = db.session.get(User, user_id) if user_id else None
    return user if user and not user.is_verified and (user.verification_nonce or '') == nonce else None


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    user = _user_to_verify()
    if not user:
        flash("Connecte-toi pour vérifier ton compte.", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = (request.form.get('code') or '').strip()

        if not user.verification_code or not user.verification_expires_at:
            flash("Aucun code actif. Cliquez sur 'Renvoyer le code'.", "error")
            return redirect(url_for('verify'))

        if user.verification_expires_at < datetime.utcnow():
            flash("Code expiré. Cliquez sur 'Renvoyer le code'.", "error")
            return redirect(url_for('verify'))

        essais = f"code:essai:{user.id}"
        if not limiteur.autoriser(essais, 5, 15 * MINUTE):
            # Trop d'erreurs : ce code ne vaut plus rien
            user.verification_code = None
            db.session.commit()
            flash("Trop d'essais. Cliquez sur 'Renvoyer le code'.", "error")
            return redirect(url_for('verify'))

        if not secrets.compare_digest(code.encode(), user.verification_code.encode()):
            flash("Code incorrect.", "error")
            return redirect(url_for('verify'))

        user.is_verified = True
        user.verification_code = None
        user.verification_expires_at = None
        db.session.commit()
        session.pop('verify', None)
        limiteur.oublier(essais)

        flash("Compte vérifié ! Vous pouvez vous connecter.", "success")
        return redirect(url_for('login'))

    return render_template('verify.html', email=user.email)


@app.route('/resend-code', methods=['POST'])
def resend_code():
    user = _user_to_verify()
    if not user:
        flash("Connecte-toi pour vérifier ton compte.", "error")
        return redirect(url_for('login'))

    if not limiteur.autoriser(f"code:envoi:{_normalize_email(user.email)}", 4, HEURE) \
            or not limiteur.autoriser(f"code:envoi-ip:{request.remote_addr}", 15, HEURE):
        flash("Trop de demandes. Réessaie dans une heure.", "error")
        return redirect(url_for('verify'))

    _new_code(user)
    db.session.commit()
    limiteur.oublier(f"code:essai:{user.id}")
    _send_code(user, "Code renvoyé par email.")
    return redirect(url_for('verify'))


# --- Mot de passe oublié ---
# La réponse est la même que l'email soit inscrit ou non : on ne révèle pas qui a un compte.

def _send_reset_email(to_email: str, code: str) -> None:
    """Envoie le code en arrière-plan : la page répond aussi vite, qu'il y ait un compte ou non."""
    def envoyer():
        try:
            _send_verification_email(to_email, code, 'reset')
        except Exception as e:
            app.logger.error("Envoi du code de réinitialisation impossible : %s", e)
            if _dev_should_show_code():
                app.logger.warning("Code DEV de réinitialisation pour %s : %s", to_email, code)

    threading.Thread(target=envoyer, daemon=True).start()


def _reset_request():
    """(email, compte) de la demande en cours dans cette session. Compte None si la demande n'est pas valable."""
    email, nonce = session.get('reset') or (None, None)
    user = _find_user(email) if email else None
    valable = user and user.is_verified and user.reset_nonce and secrets.compare_digest(user.reset_nonce, nonce or '')
    return email, (user if valable else None)


def _clear_reset(user) -> None:
    user.reset_code = None
    user.reset_expires_at = None
    user.reset_nonce = None


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        if not limiteur.autoriser(f"reset:envoi-ip:{request.remote_addr}", 10, HEURE):
            return _too_many()

        email = _normalize_email(request.form.get('email'))
        if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("L'adresse email n'est pas valide.", "error")
            return render_template('forgot_password.html')

        nonce = secrets.token_hex(16)
        session['reset'] = [email, nonce]
        user = _find_user(email)
        # Compté par email : personne ne peut inonder la boîte de quelqu'un d'autre
        if user and user.is_verified and limiteur.autoriser(f"reset:envoi:{email}", 4, HEURE):
            user.reset_code = _generate_verification_code()
            user.reset_expires_at = datetime.utcnow() + timedelta(minutes=15)
            user.reset_nonce = nonce
            db.session.commit()
            limiteur.oublier(f"reset:essai:{email}")
            _send_reset_email(user.email, user.reset_code)

        flash("Si un compte existe avec cette adresse, un code vient d'y être envoyé.", "success")
        return redirect(url_for('reset_password'))

    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    email, user = _reset_request()
    if not email:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        code = (request.form.get('code') or '').strip()
        password = request.form.get('password') or ''
        confirmation = request.form.get('password_confirm') or ''

        essais = f"reset:essai:{email}"
        if not limiteur.autoriser(essais, 5, 15 * MINUTE):
            if user:
                _clear_reset(user)  # trop d'erreurs : ce code ne vaut plus rien
                db.session.commit()
            flash("Trop d'essais. Demande un nouveau code.", "error")
            return redirect(url_for('forgot_password'))

        code_valide = (
            user and user.reset_code and user.reset_expires_at
            and user.reset_expires_at >= datetime.utcnow()
            and secrets.compare_digest(code.encode(), user.reset_code.encode())
        )
        if not code_valide:
            flash("Code incorrect ou expiré.", "error")
            return redirect(url_for('reset_password'))

        if not MDP_MIN <= len(password) <= MDP_MAX:
            erreur = f"Le mot de passe doit faire au moins {MDP_MIN} caractères."
        elif password != confirmation:
            erreur = "Les deux mots de passe ne sont pas identiques."
        elif mot_de_passe_trop_courant(password, user.username, user.email):
            erreur = "Ce mot de passe est trop facile à deviner. Choisis-en un autre."
        else:
            erreur = None
        if erreur:
            # Le code reste valable : seule la saisie du mot de passe est à refaire
            limiteur.oublier(essais)
            flash(erreur, "error")
            return render_template('reset_password.html', email=email, code=code)

        user.password = generate_password_hash(password, method='pbkdf2:sha256')
        _clear_reset(user)
        # Déconnecte tous les appareils : quelqu'un connaissait peut-être l'ancien mot de passe
        OpenSession.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        session.pop('reset', None)
        limiteur.oublier(essais)
        limiteur.oublier(f"login:compte:{email}")

        flash("Mot de passe modifié. Tu peux te connecter.", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html', email=email)


@app.route("/dashboard")
@login_required
def dashboard():

    entries = Useranime.query.filter_by(user_id=current_user.id).all()
    infos = _infos(e.anime_id for e in entries)
    anime_list = [_entry_view(e, infos.get(e.anime_id)) for e in entries]
    total_global_episodes = sum(a['current_episode'] or 0 for a in anime_list)
    total_minutes = sum(a['watched_minutes'] for a in anime_list)
    nbr_anime = sum(
        1 for a in anime_list
        if (a['current_episode'] or 0) > 0 and (not a['total_episode'] or a['current_episode'] < a['total_episode'])
    )

    # Formatage du temps total: XhYY
    total_hours = total_minutes // 60
    remaining_minutes = total_minutes % 60
    total_time_str = f"{total_hours}h{remaining_minutes:02d}"

    return render_template(
        "dashboard.html",
        animes=anime_list,
        total_vu=total_global_episodes,
        nbr_anime=nbr_anime,
        total_minutes=total_minutes,
        total_time_str=total_time_str,
    )


from deep_translator import GoogleTranslator


# Dans ta route de détail :
@app.route("/anime/<int:mal_id>")
def detail_anime(mal_id):
    if mal_id > ID_MAX:
        abort(404)
    anime_data = api.get_animes(mal_id) #
    anime = anime_data.get("data")
    if not anime:
        abort(404)

    # Bloque l'accès aux fiches adultes si l'âge n'est pas confirmé.
    if _anime_is_adult(anime) and not _age_verified():
        flash("Cet animé est marqué comme contenu adulte. Confirme 18+ pour afficher la fiche.", "warning")
        return redirect(url_for("age_gate", next=request.path))

    try:
        released = _save_info(anime).released
    except Exception as e:
        db.session.rollback()
        app.logger.warning("Infos non enregistrées : %s", e)
        released = None

    is_favorite = False
    current_episode = 0
    try:
        if current_user.is_authenticated:
            entry = Useranime.query.filter_by(user_id=current_user.id, anime_id=mal_id).first()
            is_favorite = bool(entry and entry.is_favorite)
            current_episode = (entry.current_episode or 0) if entry else 0
    except Exception:
        is_favorite = False

    # Traduction automatique
    if anime.get("synopsis"):
        try:
            traduction = GoogleTranslator(source='en', target='fr').translate(anime["synopsis"])
            anime["synopsis"] = traduction
        except:
            pass

    # Récupération des suites et préquelles
    # (secondaire : la fiche reste affichée si cet appel échoue)
    try:
        relations = api.get_relation(mal_id)
    except APIError as e:
        app.logger.warning("Relations indisponibles : %s", e)
        relations = {}
    seasons = []
    for rel in relations.get('data', []):
        if rel['relation'] in ['Sequel', 'Prequel']:
            for entry in rel['entry']:
                seasons.append(entry)

    return render_template(
        "details.html",
        anime=anime,
        seasons=seasons,
        is_favorite=is_favorite,
        current_episode=current_episode,
        released=max(released, current_episode) if released else None,
    )

def _flash_suivi(message, categorie):
    """Remplace le message de suivi en attente au lieu de l'empiler.

    Plusieurs clics rapides envoient plusieurs formulaires : le navigateur
    abandonne les pages intermédiaires, et leurs messages s'accumulaient
    jusqu'à la dernière.
    """
    session['_flashes'] = [f for f in session.get('_flashes', []) if not f[0].startswith('suivi-')]
    flash(message, categorie)


@app.route("/add_to_list", methods=["POST"])
@login_required
def add_to_list():
    # 1. Récupérer les infos envoyées par le formulaire
    anime_id = request.form.get("anime_id", type=int)
    current_ep = request.form.get("current_episode", type=int)
    total_ep = request.form.get("total_episode", type=int)
    if not anime_id or not 1 <= anime_id <= ID_MAX or not 0 <= (current_ep or 0) <= 100_000 or not 0 <= (total_ep or 0) <= 100_000:
        flash("Progression invalide.", "error")
        return redirect(_safe_referrer())

    # On reste sur la fiche, au niveau du bloc « Ma progression » où s'affiche le message
    fiche = url_for('detail_anime', mal_id=anime_id, _anchor='message-suivi')
    if _list_is_full(anime_id):
        _flash_suivi(f"Ta liste est pleine ({SUIVIS_MAX} animés).", "suivi-error")
        return redirect(fiche)

    # 2. Vérifier si cet animé est déjà dans la liste de l'utilisateur
    existing_entry = Useranime.query.filter_by(
        user_id=current_user.id,
        anime_id=anime_id
    ).first()

    if existing_entry:
        # Si oui, on met juste à jour l'épisode
        if current_ep is not None:
            existing_entry.current_episode = current_ep
        if total_ep is not None:
            existing_entry.total_episode = total_ep
    else:
        # Si non, on crée une nouvelle ligne
        new_progress = Useranime(
            user_id=current_user.id,
            anime_id=anime_id,
            current_episode=current_ep,
            total_episode=total_ep
        )
        db.session.add(new_progress)

    # 3. Sauvegarder dans la base de données
    db.session.commit()

    # 4. Confirmer sur la fiche
    vus = current_ep or 0
    if total_ep and vus >= total_ep:
        message = "Bravo, tu as vu tous les épisodes !"
    elif vus == 0:
        message = "Progression enregistrée : aucun épisode vu pour l'instant."
    else:
        message = f"Progression enregistrée : épisode {vus}."
    if not existing_entry:
        message += " L'animé est ajouté à ta progression."
    _flash_suivi(message, "suivi-success")
    return redirect(fiche)


# --- Paramètres -------------------------------------------------------------

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', adulte=_age_verified())


def _check_current_password(password: str) -> bool:
    """Vérifie le mot de passe actuel, avec un nombre d'erreurs limité par compte."""
    cle = f"settings:mdp:{current_user.id}"
    if limiteur.trop(cle, 5, 15 * MINUTE):
        flash("Trop d'essais avec un mauvais mot de passe. Réessaie dans 15 minutes.", "error")
        return False
    if len(password) <= MDP_MAX and check_password_hash(current_user.password, password):
        limiteur.oublier(cle)
        return True
    limiteur.compter(cle, 15 * MINUTE)
    flash("Mot de passe actuel incorrect.", "error")
    return False


@app.route('/settings/username', methods=['POST'])
@login_required
def change_username():
    username = (request.form.get('username') or '').strip()
    if username == current_user.username:
        flash("C'est déjà ton nom d'utilisateur.", "info")
    elif not 3 <= len(username) <= 30:
        flash("Le nom d'utilisateur doit faire entre 3 et 30 caractères.", "error")
    elif User.query.filter(db.func.lower(User.username) == username.lower(), User.id != current_user.id).first():
        flash("Ce nom d'utilisateur est déjà pris. Choisis-en un autre.", "error")
    else:
        current_user.username = username
        try:
            db.session.commit()
            flash("Nom d'utilisateur modifié.", "success")
        except IntegrityError:
            db.session.rollback()  # pris au même instant par quelqu'un d'autre
            flash("Ce nom d'utilisateur est déjà pris. Choisis-en un autre.", "error")
    return redirect(url_for('settings'))


@app.route('/settings/password', methods=['POST'])
@login_required
def change_password():
    actuel = request.form.get('current_password') or ''
    password = request.form.get('password') or ''
    confirmation = request.form.get('password_confirm') or ''
    if not _check_current_password(actuel):
        return redirect(url_for('settings'))

    if not MDP_MIN <= len(password) <= MDP_MAX:
        erreur = f"Le nouveau mot de passe doit faire au moins {MDP_MIN} caractères."
    elif password != confirmation:
        erreur = "Les deux mots de passe ne sont pas identiques."
    elif password == actuel:
        erreur = "Le nouveau mot de passe doit être différent de l'actuel."
    elif mot_de_passe_trop_courant(password, current_user.username, current_user.email):
        erreur = "Ce mot de passe est trop facile à deviner. Choisis-en un autre."
    else:
        erreur = None
    if erreur:
        flash(erreur, "error")
        return redirect(url_for('settings'))

    current_user.password = generate_password_hash(password, method='pbkdf2:sha256')
    # Déconnecte les autres appareils, garde celui-ci
    OpenSession.query.filter(
        OpenSession.user_id == current_user.id,
        OpenSession.id != _hash_token(session.get('sid', '')),
    ).delete()
    db.session.commit()
    flash("Mot de passe modifié. Tes autres appareils ont été déconnectés.", "success")
    return redirect(url_for('settings'))


@app.route('/settings/adult', methods=['POST'])
@login_required
def change_adult():
    if request.form.get('show') == 'yes':
        if request.form.get('confirm') != 'yes':
            flash("Coche la case pour confirmer que tu as 18 ans ou plus.", "error")
            return redirect(url_for('settings'))
        session['age_verified'] = True
        flash("Le contenu 18+ est maintenant affiché.", "success")
    else:
        session.pop('age_verified', None)
        flash("Le contenu 18+ est de nouveau masqué.", "success")
    return redirect(url_for('settings'))


@app.route('/settings/delete', methods=['POST'])
@login_required
def delete_account():
    if request.form.get('confirm') != 'yes':
        flash("Coche la case pour confirmer la suppression.", "error")
        return redirect(url_for('settings'))
    if not _check_current_password(request.form.get('password') or ''):
        return redirect(url_for('settings'))

    user_id = current_user.id
    Useranime.query.filter_by(user_id=user_id).delete()
    OpenSession.query.filter_by(user_id=user_id).delete()
    User.query.filter_by(id=user_id).delete()
    db.session.commit()
    limiteur.oublier(f"settings:mdp:{user_id}")
    logout_user()
    session.clear()
    flash("Ton compte et ta progression ont été supprimés.", "success")
    resp = redirect(url_for('index'))
    resp.delete_cookie(COOKIE_APPAREIL)
    return resp


def init_db() -> None:
    """Crée les tables et ajoute les colonnes manquantes (migration légère, sans Alembic)."""
    ajouts = {
        'useranime': {'is_favorite': 'BOOLEAN NOT NULL DEFAULT 0'},
        'user': {
            'is_verified': 'BOOLEAN NOT NULL DEFAULT 0',
            'verification_code': 'VARCHAR(6)',
            'verification_expires_at': 'DATETIME',
            'verification_nonce': 'VARCHAR(32)',
            'reset_code': 'VARCHAR(6)',
            'reset_expires_at': 'DATETIME',
            'reset_nonce': 'VARCHAR(32)',
        },
    }
    db.create_all()
    for table, colonnes in ajouts.items():
        presentes = {row[1] for row in db.session.execute(db.text(f"PRAGMA table_info({table})"))}
        for nom, type_sql in colonnes.items():
            if nom not in presentes:
                db.session.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {nom} {type_sql}"))
    db.session.commit()


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
