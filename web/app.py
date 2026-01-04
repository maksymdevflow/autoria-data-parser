from flask import Flask, request, jsonify
from .config.settings import DevelopmentConfig
from crud.crud_link.crud import create_new_link

app = Flask(__name__.split('.')[0])


@app.route("/")
def index():
    return "Hello, World!"


@app.route("/links", methods=["POST"])
def create_link():
    data = request.get_json(silent=True) or {}
    url = data.get("link")

    if not url:
        return jsonify({"error": "link is required"}), 400

    link_obj = create_new_link(url)

    return jsonify(
        {
            "id": link_obj.id,
            "link": link_obj.link,
            "last_processed_at": link_obj.last_processed_at,
        }
    ), 201


if __name__ == "__main__":
    config = DevelopmentConfig()
    app.config.from_object(config)
    app.run(debug=True)
