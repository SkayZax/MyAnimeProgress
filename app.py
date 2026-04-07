from deep_translator import GoogleTranslator
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from api.API import API
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
import os
import random
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import requests
from urllib.parse import urlparse, urljoin

# Chargement variables d'environnement depuis un fichier .env (si présent)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

app = Flask(__name__)
# En dev local (python app.py), on n'est généralement pas derrière un reverse proxy.
# ProxyFix peut casser les URLs si aucun header X-Forwarded-* n'est fourni.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
api = API()
# CONFIGURATION INDISPENSABLE
app.config['SECRET_KEY'] = 'ma_cle_secrete_tres_longue' # Change ceci par une phrase complexe
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # Crée un fichier database.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Si ton app est réellement montée sous un sous-chemin (ex: /MyAnimeProgress) via un reverse proxy,
# il faut configurer ça côté serveur/proxy. En dev local, ce réglage casse souvent les liens.
# app.config['APPLICATION_ROOT'] = '/MyAnimeProgress'

# Assure que les cookies de session sont valables à la racine
app.config['SESSION_COOKIE_PATH'] = '/'

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


def _is_safe_url(target: str) -> bool:
    """Empêche les redirections ouvertes (open redirect)."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _age_verified() -> bool:
    return bool(session.get("age_verified", False))


def _anime_is_adult(anime: dict) -> bool:
    """Détecte un contenu adulte via rating/genres (Jikan)."""
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
    return redirect(request.referrer or url_for("index"))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
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

    return render_template(
        "index.html",
        animes=animes,
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


def _generate_verification_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _send_verification_email(to_email: str, code: str) -> None:
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

    # Petit template HTML “propre” (sans images externes obligatoires), compatible clients mail.
    html_content = f"""\
<!doctype html>
<html lang=\"fr\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>Code de vérification</title>
  </head>
  <body style=\"margin:0;padding:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#111827;\">
    <div style=\"max-width:560px;margin:0 auto;padding:24px;\">
      <div style=\"background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;\">
        <div style=\"background:linear-gradient(90deg,#1f2937,#111827);padding:18px 20px;\">
          <div style=\"font-size:16px;font-weight:700;color:#ffffff;letter-spacing:.2px;\">MyAnimeProgress</div>
        </div>

        <div style=\"padding:22px 20px 10px 20px;\">
          <h1 style=\"margin:0 0 12px 0;font-size:18px;line-height:1.35;\">Vérifie ton compte</h1>
          <p style=\"margin:0 0 14px 0;font-size:14px;line-height:1.6;color:#374151;\">
            Voici ton code de vérification (valide <strong>15 minutes</strong>) :
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
        f"Votre code de vérification MyAnimeProgress est : {code}\n\n"
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
            'subject': 'Votre code de vérification MyAnimeProgress',
            'textContent': text_content,
            'htmlContent': html_content,
        }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    if resp.status_code >= 400:
        # Sanitize: ne pas exposer la clé API, mais donner l'info utile.
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


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    # Déconnexion Flask-Login
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
    fav_entries = Useranime.query.filter_by(user_id=current_user.id, is_favorite=True).all()
    anime_list = []
    for entry in fav_entries:
        details = api.get_animes(entry.anime_id)
        if details and 'data' in details:
            anime_list.append({
                'id': entry.anime_id,
                'title': details['data']['title'],
                'image': details['data']['images']['jpg']['large_image_url'],
                'current_episode': entry.current_episode,
                'total_episode': entry.total_episode,
            })
    return render_template('favorites.html', animes=anime_list)


@app.route('/toggle_favorite', methods=['POST'])
@login_required
def toggle_favorite():
    anime_id = request.form.get('anime_id', type=int)
    total_ep = request.form.get('total_episode', type=int)
    if not anime_id:
        return redirect(url_for('index'))

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
    return redirect(request.referrer or url_for('detail_anime', mal_id=anime_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if not user.is_verified:
                flash("Votre compte n'est pas vérifié. Entrez le code reçu par email.", "error")
                return redirect(url_for('verify', email=user.email))
            login_user(user)
            return redirect(url_for('index'))

        flash("Email ou mot de passe incorrect.", "error")
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        # 1. Vérifier si l'email existe déjà
        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash("Cet email est déjà utilisé.", "error")
            return render_template('register.html')

        # 2. Vérifier si le nom d'utilisateur existe déjà (AJOUT ICI)
        username_exists = User.query.filter_by(username=username).first()
        if username_exists:
            flash("Ce nom d'utilisateur est déjà pris. Veuillez en choisir un autre.", "error")
            return render_template('register.html')

        # Hachage du mot de passe
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')

        # Création et enregistrement du nouvel utilisateur (non vérifié)
        code = _generate_verification_code()
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        new_user = User(
            email=email,
            username=username,
            password=hashed_pw,
            is_verified=False,
            verification_code=code,
            verification_expires_at=expires_at,
        )
        db.session.add(new_user)
        db.session.commit()

        # Envoi du mail (si SMTP configuré)
        try:
            _send_verification_email(email, code)
        except Exception as e:
            # On laisse le compte créé, mais on informe l'utilisateur.
            msg = f"Compte créé, mais impossible d'envoyer l'email de vérification: {e}"
            if _dev_should_show_code():
                msg += f" (Code DEV: {code})"
            flash(msg, "error")

        return redirect(url_for('verify', email=email))

    return render_template('register.html')


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    email = request.args.get('email') or request.form.get('email')
    if not email:
        flash("Email manquant pour la vérification.", "error")
        return redirect(url_for('register'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for('register'))

    if request.method == 'POST':
        code = (request.form.get('code') or '').strip()
        now = datetime.utcnow()

        if not user.verification_code or not user.verification_expires_at:
            flash("Aucun code actif. Cliquez sur 'Renvoyer le code'.", "error")
            return redirect(url_for('verify', email=email))

        if user.verification_expires_at < now:
            flash("Code expiré. Cliquez sur 'Renvoyer le code'.", "error")
            return redirect(url_for('verify', email=email))

        if code != user.verification_code:
            flash("Code incorrect.", "error")
            return redirect(url_for('verify', email=email))

        user.is_verified = True
        user.verification_code = None
        user.verification_expires_at = None
        db.session.commit()

        flash("Compte vérifié ! Vous pouvez vous connecter.", "success")
        return redirect(url_for('login'))

    return render_template('verify.html', email=email)


@app.route('/resend-code', methods=['POST'])
def resend_code():
    email = request.form.get('email')
    if not email:
        flash("Email manquant.", "error")
        return redirect(url_for('register'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for('register'))

    if user.is_verified:
        flash("Compte déjà vérifié.", "success")
        return redirect(url_for('login'))

    code = _generate_verification_code()
    user.verification_code = code
    user.verification_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()

    try:
        _send_verification_email(user.email, code)
        flash("Code renvoyé par email.", "success")
    except Exception as e:
        msg = f"Impossible d'envoyer l'email: {e}"
        if _dev_should_show_code():
            msg += f" (Code DEV: {code})"
        flash(msg, "error")
    return redirect(url_for('verify', email=user.email))


@app.route("/dashboard")
@login_required
def dashboard():

    user_animes = Useranime.query.filter_by(user_id=current_user.id).all()
    total_global_episodes = 0
    total_minutes = 0
    nbr_anime = 0
    anime_list = []


    for entry in user_animes:
        total_global_episodes += (entry.current_episode or 0)
        if (entry.current_episode or 0) > 0:
            if entry.total_episode is None or entry.total_episode == 0 or entry.current_episode < entry.total_episode:
                nbr_anime += 1
        details = api.get_animes(entry.anime_id)
        if details and 'data' in details:
            # Durée moyenne d'un épisode (minutes) – via Jikan: ex "23 min per ep"
            duration_str = (details['data'].get('duration') or "").lower()
            duration_min = 0
            try:
                # Cas le plus courant: "23 min per ep"
                if "min" in duration_str:
                    duration_min = int(duration_str.split("min")[0].strip())
            except Exception:
                duration_min = 0

            # Fallback si durée inconnue (on prend 24 min)
            if duration_min <= 0:
                duration_min = 24

            watched_eps = int(entry.current_episode or 0)
            total_minutes += watched_eps * duration_min

            anime_info = {
                'id': entry.anime_id,
                'title': details['data']['title'],
                'image': details['data']['images']['jpg']['large_image_url'],
                'current_episode': entry.current_episode,
                'total_episode': entry.total_episode,
                'duration_min': duration_min,
                'watched_minutes': watched_eps * duration_min,
            }
            anime_list.append(anime_info)

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
    anime_data = api.get_animes(mal_id) #
    anime = anime_data.get("data", {})

    # Bloque l'accès aux fiches adultes si l'âge n'est pas confirmé.
    if _anime_is_adult(anime) and not _age_verified():
        flash("Cet animé est marqué comme contenu adulte. Confirme 18+ pour afficher la fiche.", "warning")
        return redirect(url_for("age_gate", next=request.path))

    is_favorite = False
    try:
        if current_user.is_authenticated:
            entry = Useranime.query.filter_by(user_id=current_user.id, anime_id=mal_id).first()
            is_favorite = bool(entry and entry.is_favorite)
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
    relations = api.get_relation(mal_id)
    seasons = []
    for rel in relations.get('data', []):
        if rel['relation'] in ['Sequel', 'Prequel']:
            for entry in rel['entry']:
                seasons.append(entry)

    return render_template("details.html", anime=anime, seasons=seasons, is_favorite=is_favorite)
@app.route("/add_to_list", methods=["POST"])
@login_required
def add_to_list():
    # 1. Récupérer les infos envoyées par le formulaire
    anime_id = request.form.get("anime_id", type=int)
    current_ep = request.form.get("current_episode", type=int)
    total_ep = request.form.get("total_episode", type=int)

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

    # 4. Rediriger vers le dashboard pour voir le résultat
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    with app.app_context():
        # Crée les tables si elles n'existent pas
        db.create_all()

        # --- Migration légère SQLite (sans Alembic) ---
        # Si on a ajouté des colonnes au modèle, SQLite ne les crée pas tout seul.
        # On ajoute ici useranime.is_favorite si elle n'existe pas.
        try:
            cols = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(useranime)")).fetchall()]
            if 'is_favorite' not in cols:
                db.session.execute(db.text("ALTER TABLE useranime ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0"))
                db.session.commit()
        except Exception:
            # Ne bloque pas le démarrage si jamais la DB est dans un état inattendu
            db.session.rollback()

        # Migration: vérification email sur la table user
        try:
            user_cols = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(user)")).fetchall()]
            if 'is_verified' not in user_cols:
                db.session.execute(db.text("ALTER TABLE user ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT 0"))
            if 'verification_code' not in user_cols:
                db.session.execute(db.text("ALTER TABLE user ADD COLUMN verification_code VARCHAR(6)"))
            if 'verification_expires_at' not in user_cols:
                db.session.execute(db.text("ALTER TABLE user ADD COLUMN verification_expires_at DATETIME"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        print("Base de données initialisée !")
        app.run(debug=True)