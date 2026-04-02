from deep_translator import GoogleTranslator
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from api.API import API
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user
import os

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
api = API()
# CONFIGURATION INDISPENSABLE
app.config['SECRET_KEY'] = 'ma_cle_secrete_tres_longue' # Change ceci par une phrase complexe
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # Crée un fichier database.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Gestion de la connexion
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
@app.route("/", methods=["GET"])
def index():
    page = request.args.get('page', 1, type=int)
    genre_name= request.args.get('genres', type=str)
    title=""
    animes = api.get_animepage(page)
    if genre_name == 'Action':
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

    return render_template("index.html", animes=animes, current_page=page,)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Useranime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    anime_id = db.Column(db.Integer, nullable=False)
    current_episode = db.Column(db.Integer, default=0)
    total_episode = db.Column(db.Integer, nullable=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
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
            return "Cet email est déjà utilisé."

        # 2. Vérifier si le nom d'utilisateur existe déjà (AJOUT ICI)
        username_exists = User.query.filter_by(username=username).first()
        if username_exists:
            return "Ce nom d'utilisateur est déjà pris. Veuillez en choisir un autre."

        # Hachage du mot de passe
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')

        # Création et enregistrement du nouvel utilisateur
        new_user = User(email=email, username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route("/dashboard")
@login_required
def dashboard():

    user_animes = Useranime.query.filter_by(user_id=current_user.id).all()
    total_global_episodes=0
    nbr_anime=0
    anime_list = []


    for entry in user_animes:
        total_global_episodes += (entry.current_episode or 0)
        if (entry.current_episode or 0) > 0:
            if entry.total_episode is None or entry.total_episode == 0 or entry.current_episode < entry.total_episode:
                nbr_anime += 1
        details = api.get_animes(entry.anime_id)
        if details and 'data' in details:
            anime_info = {
                'id': entry.anime_id,
                'title': details['data']['title'],
                'image': details['data']['images']['jpg']['large_image_url'],
                'current_episode': entry.current_episode,
                'total_episode': entry.total_episode
            }
            anime_list.append(anime_info)

    return render_template("dashboard.html", animes=anime_list, total_vu=total_global_episodes, nbr_anime=nbr_anime)


from deep_translator import GoogleTranslator


# Dans ta route de détail :
@app.route("/anime/<int:mal_id>")
def detail_anime(mal_id):
    anime_data = api.get_animes(mal_id)
    anime = anime_data.get("data", {})

    # Traduction du synopsis s'il existe
    if anime.get("synopsis"):
        traduction = GoogleTranslator(source='en', target='fr').translate(anime["synopsis"])
        anime["synopsis"] = traduction

    return render_template("details.html", anime=anime)


@app.route("/anime/<int:anime_id>")
def details(anime_id):
    anime_data = api.get_animes(anime_id)

    relations = api.get_relations(anime_id)

    # 3. Filtrer pour ne garder que les Sequel (suites) et Prequel (précédents)
    seasons = []
    for rel in relations.get('data', []):
        if rel['relation'] in ['Sequel', 'Prequel']:
            for entry in rel['entry']:
                seasons.append(entry)

    return render_template("details.html", anime=anime_data['data'], seasons=seasons)
@app.route("/add_to_list", methods=["POST"])
@login_required
def add_to_list():
    # 1. Récupérer les infos envoyées par le formulaire
    anime_id = request.form.get("anime_id")
    current_ep = request.form.get("current_episode")
    total_ep = request.form.get("total_episode")

    # 2. Vérifier si cet animé est déjà dans la liste de l'utilisateur
    existing_entry = Useranime.query.filter_by(
        user_id=current_user.id,
        anime_id=anime_id
    ).first()

    if existing_entry:
        # Si oui, on met juste à jour l'épisode
        existing_entry.current_episode = current_ep
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
        print("Base de données initialisée !")
        app.run(debug=True)
