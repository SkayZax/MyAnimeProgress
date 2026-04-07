# Configuration email (Mailtrap) – MyAnimeProgress

## Objectif
Activer l’envoi du code de vérification par email lors de l’inscription.

L’application lit la configuration SMTP depuis les variables d’environnement (fichier `.env` recommandé) et envoie un code à 6 chiffres.

## 1) Récupérer les identifiants SMTP sur Mailtrap
1. Crée un compte sur https://mailtrap.io
2. Crée une **Inbox** (ou utilise celle par défaut)
3. Dans l’inbox → **SMTP Settings**
4. Copie :
   - **Host**
   - **Port** (souvent 587)
   - **Username**
   - **Password**

## 2) Créer le fichier `.env`
À la racine du projet, crée un fichier **`.env`** (ne pas le commit) et mets :

```dotenv
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=VOTRE_USER
SMTP_PASSWORD=VOTRE_PASSWORD
SMTP_FROM=MyAnimeProgress <no-reply@myanimeprogress.local>

# DEV: affiche le code à l'écran si l'envoi mail échoue
DEV_SHOW_VERIFICATION_CODE=1
```

> Note : certains comptes Mailtrap affichent un host différent. Prends **exactement** celui fourni dans ton Inbox.

## 3) Installer la dépendance
Le projet charge automatiquement `.env` via `python-dotenv`.

```powershell
python -m pip install python-dotenv
```

## 4) Lancer l’application
```powershell
cd "C:\Users\SkayZax\Documents\BUT2\animelist"
python app.py
```

## 5) Test
1. Va sur `/register` et crée un compte
2. Tu es redirigé vers `/verify`
3. Récupère l’email dans Mailtrap, copie le code
4. Entre le code → le compte passe vérifié
5. Connecte-toi ensuite sur `/login`

## Dépannage
- Message `SMTP non configuré ...` : ton fichier `.env` n’est pas chargé (ou il manque des clés).
- Auth error : `SMTP_USER/SMTP_PASSWORD` incorrects.
- Aucun email : vérifie l’inbox Mailtrap et que les identifiants SMTP correspondent à cette inbox.

