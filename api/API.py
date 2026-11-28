import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIError(Exception):
    """L'API d'animes est injoignable ou a renvoye une reponse inutilisable."""


class API:
    # (connexion, lecture) en secondes
    TIMEOUT = (5, 10)
    # Duree de memorisation des episodes sortis, en secondes
    RELEASED_TTL = 6 * 3600
    RELEASED_TTL_ERROR = 10 * 60
    # Duree de memorisation des fiches d'une selection (onglet Classiques), en secondes
    SELECTION_TTL = 12 * 3600

    def __init__(self):
        # Tenrai reprend le format de Jikan v4 (API publique fermee le 1er octobre 2026)
        self.url_api = "https://api.tenrai.org/v1/anime"
        self._released = {}  # anime_id -> (expiration, nombre ou None)
        self._fiches = {}  # anime_id -> (expiration, fiche)
        self._fiches_verrou = threading.Lock()  # une seule mise à jour de sélection à la fois
        self.session = requests.Session()
        # Coupure : un nouvel essai. Limite de debit ou erreur serveur : deux, dont un apres ~2 s
        retry = Retry(
            total=2,
            connect=1,
            read=1,
            backoff_factor=1,
            backoff_jitter=0.5,
            status_forcelist=(429, 502, 503, 504),
            respect_retry_after_header=False,
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get(self, url: str, params: dict | None = None) -> dict:
        """Renvoie le JSON, {} si la ressource n'existe pas, ou leve APIError."""
        try:
            result = self.session.get(url, params=params, timeout=self.TIMEOUT)
            if result.status_code == 404:
                return {}
            result.raise_for_status()
            return result.json()
        except requests.exceptions.RequestException as e:
            raise APIError(f"{url} : {e}") from e

    def get_animes(self, anime_id: int) -> dict:
        return self._get(f"{self.url_api}/{anime_id}")

    def gettitlefromjson(self,anime_json: dict) -> str:
        return anime_json["data"]["title"]

    def get_popular(self, page: int = 1) -> list:
        """Animés classés par popularité (nombre de membres sur MyAnimeList)."""
        data = self._get(self.url_api.rsplit("/", 1)[0] + "/top/anime", {"filter": "bypopularity", "page": page})
        return data.get("data", [])

    def get_top_rated(self, page: int = 1) -> list:
        """Animés classés par note (classement officiel de MyAnimeList)."""
        data = self._get(self.url_api.rsplit("/", 1)[0] + "/top/anime", {"page": page})
        return data.get("data", [])

    def get_selection(self, ids: list) -> list:
        """Fiches d'une liste d'animés choisis, du plus suivi au moins suivi.

        Gardées en mémoire SELECTION_TTL. Une fiche périmée est servie telle quelle
        pendant qu'un fil la relit en arrière-plan : seul le tout premier affichage attend l'API.
        """
        now = time.monotonic()
        absents = [i for i in ids if i not in self._fiches]
        if absents:
            self._charger(absents)
            if not any(i in self._fiches for i in ids):
                raise APIError("aucune fiche de la sélection n'a répondu")
        elif any(self._fiches[i][0] <= now for i in ids):
            self.prechauffer(ids)
        fiches = [self._fiches[i][1] for i in ids if i in self._fiches]
        return sorted(fiches, key=lambda f: f.get("members") or 0, reverse=True)

    def prechauffer(self, ids: list) -> None:
        """Relit en arrière-plan les fiches absentes ou périmées d'une sélection."""
        now = time.monotonic()
        a_lire = [i for i in ids if self._fiches.get(i, (0, None))[0] <= now]
        if a_lire:
            threading.Thread(target=self._charger, args=(a_lire,), daemon=True).start()

    def _charger(self, ids: list) -> None:
        # Deux appels à la fois : au-delà, l'API répond « trop de requêtes »
        if not self._fiches_verrou.acquire(timeout=30):
            return
        try:
            # Un autre fil vient peut-être de les lire pendant qu'on attendait
            now = time.monotonic()
            ids = [i for i in ids if self._fiches.get(i, (0, None))[0] <= now]

            def lire(anime_id):
                try:
                    return anime_id, self.get_animes(anime_id).get("data")
                except APIError:
                    return anime_id, None

            with ThreadPoolExecutor(max_workers=2) as pool:
                for anime_id, fiche in pool.map(lire, ids):
                    if fiche:
                        self._fiches[anime_id] = (time.monotonic() + self.SELECTION_TTL, fiche)
        finally:
            self._fiches_verrou.release()

    def get_animepage(self,page: int=1)->list:
        data = self._get(self.url_api, {"page": page})
        return data.get("data",[])

    def images(self,anime_json: dict)->str:
        return anime_json["images"]["jpg"]["large_image_url"]
    def get_synopsis(self,anime_json: dict)-> str:
        return anime_json["data"]["synopsis"]
    def get_anime_genres(self,anime_json: dict)->list:
        return anime_json["data"]["genres"]

    def get_animes_by_genre(self, genre_id: int, page: int = 1) -> list:

        params = {
            "genres": genre_id,
            "page": page
        }
        data = self._get(self.url_api, params)
        return data.get("data", [])

    def get_released_episodes(self, anime_id: int) -> int | None:
        """Nombre d'episodes deja sortis (series en cours), ou None si inconnu.

        Relu regulierement et jamais stocke en base, car il change chaque semaine.
        """
        now = time.monotonic()
        expires, count = self._released.get(anime_id, (0, None))
        if now < expires:
            return count

        url = f"{self.url_api}/{anime_id}/episodes"
        ttl = self.RELEASED_TTL
        try:
            page = self._get(url)
            last = (page.get("pagination") or {}).get("last_visible_page") or 1
            if last > 1:
                page = self._get(url, {"page": last})
            numbers = [e["mal_id"] for e in page.get("data") or [] if e.get("mal_id")]
            count = max(numbers, default=None)
        except APIError:
            # Information secondaire : on garde la derniere valeur connue
            ttl = self.RELEASED_TTL_ERROR
        self._released[anime_id] = (now + ttl, count)
        return count

    def get_relation(self, anime_id: int) -> dict:
        return self._get(f"{self.url_api}/{anime_id}/relations")

    def search_anime(self, query: str, page: int = 1) -> list:
        params = {
            "q": query,
            "page": page
        }
        data = self._get(self.url_api, params)
        return data.get("data", [])