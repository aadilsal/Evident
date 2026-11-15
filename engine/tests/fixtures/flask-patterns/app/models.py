from .extensions import db


class Base(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def first_by(cls, **kwargs):
        return cls.query.filter_by(**kwargs).first()

    @classmethod
    def get(cls, _id):
        return cls.query.get(_id)


class User(Base):
    __tablename__ = "users"
    email = db.Column(db.String(200))
