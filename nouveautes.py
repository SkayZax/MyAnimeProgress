"""Notes de mise à jour affichées dans la pop-up « Nouveautés ».

Pour annoncer une mise à jour, ajoute une entrée EN HAUT de la liste avec une
nouvelle `version` : la pop-up se rouvrira une fois chez chaque visiteur.

Le titre a deux graisses, comme le logo : `titre` en gras, `suite` en maigre.
Icônes possibles (templates/_icones.html) : accueil, etoile, reprise, catalogue,
reglages, fiche, cle, palette, calendrier, bouclier.
"""

NOUVEAUTES = [
    {
        'version': '2026-11-28',
        'date': '28 novembre 2026',
        'titre': "L'accueil",
        'suite': 'fait peau neuve',
        'resume': "Plus de choses à découvrir dès la première page, et plus de réglages pour ton compte.",
        'points': [
            {'icone': 'accueil', 'titre': 'Trois listes sur l’accueil',
             'texte': 'Populaires, Mieux notés et Classiques, en un clic.'},
            {'icone': 'etoile', 'titre': 'Le top 3 mis en avant',
             'texte': 'Avec sa note et son nombre de membres.'},
            {'icone': 'reprise', 'titre': 'Reprends tes séries',
             'texte': 'Tes animés en cours t’attendent en haut de l’accueil.'},
            {'icone': 'catalogue', 'titre': 'Un vrai catalogue',
             'texte': 'Tous les animés, la recherche et les genres sur leur propre page.'},
            {'icone': 'reglages', 'titre': 'Page Paramètres',
             'texte': 'Pseudo, mot de passe, contenu 18+ et suppression du compte.'},
            {'icone': 'fiche', 'titre': 'Tu restes sur la fiche',
             'texte': 'Après avoir enregistré un épisode, plus besoin de la rechercher.'},
        ],
    },
    {
        'version': '2026-11-27',
        'date': '27 novembre 2026',
        'titre': 'Mot de passe',
        'suite': 'oublié',
        'resume': "Tu ne restes plus bloqué dehors.",
        'points': [
            {'icone': 'cle', 'titre': 'Réinitialisation par email',
             'texte': 'Un code reçu par email suffit pour choisir un nouveau mot de passe.'},
        ],
    },
    {
        'version': '2026-11-24',
        'date': '24 novembre 2026',
        'titre': 'Nouvelle',
        'suite': 'direction artistique',
        'resume': "Le site change de tête, et gagne en fiabilité.",
        'points': [
            {'icone': 'palette', 'titre': 'Noir et rouge',
             'texte': 'Tout le site repensé autour du logo.'},
            {'icone': 'calendrier', 'titre': 'Épisodes sortis',
             'texte': 'Le nombre d’épisodes déjà diffusés s’affiche pour les séries en cours.'},
            {'icone': 'fiche', 'titre': 'Ta progression sur la fiche',
             'texte': 'La fiche montre l’épisode où tu en es.'},
            {'icone': 'bouclier', 'titre': 'Comptes mieux protégés',
             'texte': 'Connexion et formulaires renforcés.'},
        ],
    },
]
