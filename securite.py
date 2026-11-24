"""Limitation du nombre d'essais, en mémoire.

Les compteurs vivent dans le processus : gunicorn doit tourner avec un seul worker
(plusieurs threads conviennent), et un redémarrage les remet à zéro.
"""
import re
import threading
import time
from collections import deque


class Limiteur:
    MAX_CLES = 10_000

    def __init__(self):
        self._essais = {}  # clé -> (fenêtre, instants des essais)
        self._verrou = threading.Lock()

    def trop(self, cle: str, limite: int, fenetre: int) -> bool:
        """Vrai si la limite est atteinte. N'enregistre rien."""
        with self._verrou:
            return len(self._recents(cle, fenetre)) >= limite

    def compter(self, cle: str, fenetre: int) -> None:
        """Enregistre un essai."""
        with self._verrou:
            if cle not in self._essais and len(self._essais) >= self.MAX_CLES:
                self._purger()
            recents = self._recents(cle, fenetre)
            recents.append(time.monotonic())
            self._essais[cle] = (fenetre, recents)

    def autoriser(self, cle: str, limite: int, fenetre: int) -> bool:
        """Enregistre l'essai et renvoie Vrai, sauf si la limite est atteinte."""
        if self.trop(cle, limite, fenetre):
            return False
        self.compter(cle, fenetre)
        return True

    def oublier(self, cle: str) -> None:
        with self._verrou:
            self._essais.pop(cle, None)

    def _recents(self, cle, fenetre):
        _, instants = self._essais.get(cle, (fenetre, deque()))
        debut = time.monotonic() - fenetre
        while instants and instants[0] < debut:
            instants.popleft()
        return instants

    def _purger(self):
        for cle, (fenetre, _) in list(self._essais.items()):
            if not self._recents(cle, fenetre):
                del self._essais[cle]
        # Toujours plein (attaque) : on retire les clés les plus anciennes
        for cle in list(self._essais)[:max(0, len(self._essais) - self.MAX_CLES + 1)]:
            del self._essais[cle]


_COURANTS = set("""
password passwort motdepasse mdp azerty azertyuiop qwerty qwertyuiop qwertz admin administrateur
administrator root welcome bienvenue letmein iloveyou jetaime bonjour soleil loulou doudou chouchou
marseille paris france football princess princesse dragon monkey shadow sunshine superman batman
starwars pokemon naruto onepiece dragonball anime manga myanimeprogress trustno secret changeme
computer ordinateur internet samsung google facebook master killer freedom liberte amour coucou
nicolas camille thomas julien chocolat papillon vacances test testtest user utilisateur guest
michael jordan charlie ashley baseball basketball hockey soccer ninja mustang access passw
qsdfghjklm asdfghjkl wxcvbn zxcvbnm azeqsd abcdefgh abcdefghi abcd abcde abcdef abc qazwsx
""".split())
_SUITES = ("01234567890123456789", "98765432109876543210", "abcdefghijklmnopqrstuvwxyz",
           "azertyuiopqsdfghjklmwxcvbn", "qwertyuiopasdfghjklzxcvbnm")
_LEET = str.maketrans("@4831!05$7", "aaeeiiosst")


def mot_de_passe_trop_courant(mdp: str, pseudo: str = "", email: str = "") -> bool:
    """Vrai pour les mots de passe que les attaquants essaient en premier."""
    bas = mdp.lower()
    if len(set(bas)) < 4 or any(bas in suite for suite in _SUITES):
        return True
    perso = {p for p in (pseudo.lower(), email.split("@")[0].lower(), email.lower()) if len(p) >= 4}
    for forme in (bas, bas.translate(_LEET)):
        coeur = re.sub(r"^[^a-z]+|[^a-z]+$", "", forme)
        # Mot courant ou répété, entouré de chiffres ou de symboles : "Password1!", "azerty123", "testtest"
        moitie = coeur[:len(coeur) // 2]
        if coeur in _COURANTS or (moitie in _COURANTS and coeur == moitie * 2):
            return True
        if any(forme == p or coeur == re.sub(r"^[^a-z]+|[^a-z]+$", "", p) for p in perso):
            return True
    # Blocs répétés : "12341234", "abcabcabc"
    return any(len(bas) % n == 0 and bas == bas[:n] * (len(bas) // n) for n in range(1, 5))
