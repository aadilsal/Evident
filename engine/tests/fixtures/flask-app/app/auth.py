from flask import Blueprint, request

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    return {"user": data.get("email")}
