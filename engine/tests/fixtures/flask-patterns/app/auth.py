from flask import Blueprint

from .models import User

auth_blueprint = Blueprint("auth", __name__)


@auth_blueprint.route("/auth/login", methods=["POST"])
def login():
    user = User.first_by(email="a@example.com")
    return {"id": user.id}
