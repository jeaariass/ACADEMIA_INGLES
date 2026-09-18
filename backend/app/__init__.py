import logging
import os

from flask import Flask, g, jsonify, render_template, request, redirect, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."
login_manager.session_protection = "strong"


def _is_production():
    return (os.getenv("APP_ENV") or "development").strip().lower() == "production"


def _error_response(status_code, title, message):
    request_id = getattr(g, "request_id", None)
    if request.path.startswith("/game/api/") or request.path.startswith("/api/") or request.is_json:
        return jsonify({
            "ok": False,
            "error": message,
            "request_id": request_id,
        }), status_code
    return render_template(
        "error.html",
        status_code=status_code,
        title=title,
        message=message,
        request_id=request_id,
    ), status_code


def create_app():
    app = Flask(__name__)

    secret = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    if _is_production() and secret in {
        "dev-secret-change-me",
        "change-this-secret",
        "dev-local-secret-key",
        "",
    }:
        raise RuntimeError(
            "FLASK_SECRET_KEY must be set to a strong unique value when APP_ENV=production."
        )

    app.config["SECRET_KEY"] = secret
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///english_local.db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
    )

    log_level = (os.getenv("LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    from .security import init_security
    init_security(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from .routes import main_bp
    from .auth import auth_bp
    from .admin import admin_bp
    from .assessment import assessment_bp
    from .game_vocab_admin import bp as game_vocab_admin_bp
    from .question_import import question_import_bp
    from .library import library_bp
    from .game import game_bp
    from .insights import insights_bp
    from .speaking import speaking_bp
    from .writing import writing_bp
    from .arcade import arcade_bp
    from .kids import kids_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(assessment_bp)
    app.register_blueprint(game_vocab_admin_bp)
    app.register_blueprint(question_import_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(game_bp)
    app.register_blueprint(insights_bp)
    app.register_blueprint(speaking_bp)
    app.register_blueprint(writing_bp)
    app.register_blueprint(arcade_bp)
    app.register_blueprint(kids_bp)

    @app.before_request
    def enforce_kids_mode():
        if not current_user.is_authenticated or not getattr(current_user, "is_kids_mode", False):
            return None
        endpoint = request.endpoint or ""
        if endpoint in {"healthz", "readyz", "static", "auth.logout"} or endpoint.startswith("kids."):
            return None
        if endpoint in {"main.index", "main.dashboard"}:
            return redirect(url_for("kids.index"))
        # Kids accounts intentionally cannot enter formal/adult learning modules.
        return redirect(url_for("kids.index"))

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True, "service": "english-practice-hub"})

    @app.get("/readyz")
    def readyz():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            app.logger.exception("Database readiness check failed")
            return jsonify({"ok": False, "database": "unavailable"}), 503
        return jsonify({"ok": True, "database": "ready"})

    @app.errorhandler(400)
    def bad_request(_error):
        return _error_response(400, "Invalid request", "The request could not be processed safely.")

    @app.errorhandler(403)
    def forbidden(_error):
        return _error_response(403, "Access denied", "You do not have permission to access this resource.")

    @app.errorhandler(404)
    def not_found(_error):
        return _error_response(404, "Page not found", "The requested page does not exist or is no longer available.")

    @app.errorhandler(413)
    def too_large(_error):
        return _error_response(413, "File too large", "The uploaded file exceeds the configured size limit.")

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception(
            "Unhandled application error request_id=%s",
            getattr(g, "request_id", None),
            exc_info=error,
        )
        return _error_response(
            500,
            "Something went wrong",
            "The operation could not be completed. No technical details were exposed.",
        )

    return app
