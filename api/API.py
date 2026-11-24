import time

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

    def __init__(self):
        # Tenrai reprend le format de Jikan v4 (API publique fermee le 1er octobre 2026)
        self.url_api = "https://api.tenrai.org/v1/anime"
        self._released = {}  # anime_id -> (expiration, nombre ou None)
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