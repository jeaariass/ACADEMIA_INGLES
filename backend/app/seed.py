import os

from . import db
from .models import User


def ensure_user(username, full_name, role, password):
    user = User.query.filter_by(username=username).first()

    if not user:
        user = User(username=username, full_name=full_name, role=role)
        user.set_password(password)
        db.session.add(user)

    return user


def seed_initial_data():
    """Create initial users only. Academic content is imported from JSON files."""

    ensure_user(
        os.getenv("ADMIN_USERNAME", "admin"),
        "Administrator",
        "admin",
        os.getenv("ADMIN_PASSWORD", "Admin123*"),
    )

    ensure_user(
        os.getenv("STUDENT1_USERNAME", "student1"),
        "Student 1",
        "student",
        os.getenv("STUDENT1_PASSWORD", "Student123*"),
    )

    ensure_user(
        os.getenv("STUDENT2_USERNAME", "student2"),
        "Student 2",
        "student",
        os.getenv("STUDENT2_PASSWORD", "Student123*"),
    )

    db.session.commit()
