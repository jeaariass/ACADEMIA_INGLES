import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.models import User


app = create_app()

with app.app_context():
    users = User.query.order_by(User.id).all()

    print("Users in current database:")

    if not users:
        print("- No users found.")
    else:
        for user in users:
            print(
                f"- {user.username} | "
                f"{user.full_name} | "
                f"{user.role}"
            )
