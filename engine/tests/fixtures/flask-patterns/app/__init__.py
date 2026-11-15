from .api import user_blueprints
from .base import BaseFlask


def create_app():
    app = BaseFlask(__name__)
    # A function-local import, as Flask app factories often do to avoid import cycles.
    from .auth_api import auth_blueprints

    blueprints = [*auth_blueprints, *user_blueprints]
    for blueprint in blueprints:
        app.register_blueprint(blueprint, url_prefix="/v1")
    return app
