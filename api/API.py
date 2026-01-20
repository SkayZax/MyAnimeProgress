import requests
class API:
    def __init__(self):
        self.url_api = "https://api.jikan.moe/v4/anime/"

    def get_animes(self,anime_id: int)->dict:
        result=requests.get(self.url_api+str(anime_id))
        return  result.json()

    def gettitlefromjson(self,anime_json: dict) -> str:
        return anime_json["data"]["title"]

    def get_animepage(self,page: int=1)->list:
        result=requests.get(self.url_api,params={"page":page})
        data=result.json()
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
        result = requests.get(self.url_api, params=params)
        data = result.json()
        return data.get("data", [])
