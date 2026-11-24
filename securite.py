"""Limitation du nombre d'essais, en mémoire.

Les compteurs vivent dans le processus : gunicorn doit tourner avec un seul worker
(plusieurs threads conviennent), et un redémarrage les remet à zéro.
"""
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
