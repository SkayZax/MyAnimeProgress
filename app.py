from flask import Flask, render_template, request
from api.API import API
app=Flask(__name__)
api=API()
@app.route("/", methods=["GET"])
def index():
    page = request.args.get('page', 1, type=int)

    animes = api.get_animepage(page)

    return render_template("index.html", animes=animes, current_page=page)




if __name__ == "__main__":
    app.run(debug=True)
