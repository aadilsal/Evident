from flask import Flask

from .auth import bp as auth_bp
from .posts import posts


def create_app():
    app = Flask(__name__)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(posts)
    return app
