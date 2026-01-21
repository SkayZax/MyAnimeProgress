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
    if genre_name=='Sports':
        animes=api.get_animes_by_genre(genre_id=30, page=page)
    elif genre_name == 'Action':
        animes = api.get_animes_by_genre(genre_id=1, page=page)
    else:
        animes = api.get_animepage(page)

    return render_template("index.html", animes=animes, current_page=page,)





if __name__ == "__main__":
    app.run(debug=True)
