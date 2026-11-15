from flask import Blueprint

from .models import User

users_blueprint = Blueprint("users", __name__)


@users_blueprint.get("/users/<int:user_id>")
def get_user(user_id):
    return {"id": User.get(user_id).id}
