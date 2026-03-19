from flask import Flask, render_template, request, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from api.API import API
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required  # Ajout de LoginManager
import os

app = Flask(__name__)
api = API()

# CONFIGURATION INDISPENSABLE
app.config['SECRET_KEY'] = 'ma_cle_secrete_tres_longue' # Change ceci par une phrase complexe
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # Crée un fichier database.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Gestion de la connexion
login_manager = LoginManager()
login_manager.init_app(app)

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


@app.route('/login', methods=['GET', 'POST'])  # On ajoute GET ici
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))  # Redirige vers l'accueil après connexion

        return "Email ou mot de passe incorrect."

    # Si c'est un GET, on affiche simplement le formulaire
    return render_template('login.html')


@app.route("/register", methods=["GET", "POST"])
def register():
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
    return render_template("dashboard.html")

if __name__ == "__main__":
    with app.app_context():
        # Crée les tables si elles n'existent pas
        db.create_all()
        print("Base de données initialisée !")
        app.run(debug=True)
