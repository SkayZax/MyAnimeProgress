from flask import Flask, render_template, request
from api.API import API
app=Flask(__name__)
api=API()
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





if __name__ == "__main__":
    app.run(debug=True)
