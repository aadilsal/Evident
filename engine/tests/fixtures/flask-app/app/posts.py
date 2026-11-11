from flask import Blueprint, request
from flask_login import login_required

from .extensions import db
from .models import Post

posts = Blueprint("posts", __name__, url_prefix="/posts")


@posts.get("/")
def list_posts():
    return [p.title for p in Post.query.all()]


@posts.post("/")
@login_required
def create_post():
    post = Post(title=request.json["title"])
    db.session.add(post)
    db.session.commit()
    return {"id": post.id}


@posts.route("/<int:post_id>", methods=["DELETE"])
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)
    db.session.delete(post)
    db.session.commit()
    return "", 204
