"""PixelCoin — premium crypto banking platform."""

import os
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import select

from models import ADMIN_EMAIL, ADMIN_PASSWORD, User, db

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to access this page."
login_manager.login_message_category = "info"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "pixelcoin-dev-secret-change-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///pixelcoin.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_user():
        return {"current_user": current_user, "ADMIN_EMAIL": ADMIN_EMAIL}

    with app.app_context():
        db.create_all()
        _seed_admin()

    register_routes(app)
    return app


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_administrator:
            flash("Admin access required.", "error")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped


def _seed_admin() -> None:
    admin = db.session.scalar(select(User).where(User.email == ADMIN_EMAIL))
    if admin is None:
        admin = User(email=ADMIN_EMAIL, is_admin=True)
        admin.set_password(ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()
    elif not admin.is_admin:
        admin.is_admin = True
        db.session.commit()


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if not email or not password:
                flash("Email and password are required.", "error")
            elif len(password) < 4:
                flash("Password must be at least 4 characters.", "error")
            elif password != confirm:
                flash("Passwords do not match.", "error")
            elif db.session.scalar(select(User).where(User.email == email)):
                flash("An account with this email already exists.", "error")
            else:
                user = User(
                    email=email,
                    is_admin=(email == ADMIN_EMAIL.lower()),
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash("Account created successfully. Welcome to PixelCoin!", "success")
                if user.is_administrator:
                    return redirect(url_for("admin"))
                return redirect(url_for("index"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = db.session.scalar(select(User).where(User.email == email))
            if user is None or not user.check_password(password):
                flash("Invalid email or password.", "error")
            else:
                if email == ADMIN_EMAIL.lower() and not user.is_admin:
                    user.is_admin = True
                    db.session.commit()
                login_user(user, remember=bool(request.form.get("remember")))
                flash(f"Welcome back, {user.email}!", "success")
                next_page = request.args.get("next")
                if user.is_administrator:
                    return redirect(next_page or url_for("admin"))
                return redirect(next_page or url_for("index"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been signed out.", "info")
        return redirect(url_for("index"))

    @app.route("/admin")
    @admin_required
    def admin():
        users = db.session.scalars(select(User).order_by(User.created_at.desc())).all()
        admin_count = sum(1 for u in users if u.is_administrator)
        return render_template("admin.html", users=users, admin_count=admin_count)

    @app.route("/admin/users/<int:user_id>/toggle-admin", methods=["POST"])
    @admin_required
    def toggle_admin(user_id: int):
        user = db.session.get(User, user_id)
        if user is None:
            flash("User not found.", "error")
            return redirect(url_for("admin"))

        if user.id == current_user.id:
            flash("You cannot change your own admin role.", "error")
            return redirect(url_for("admin"))

        if user.email.lower() == ADMIN_EMAIL.lower():
            flash("This account is the primary admin and cannot be changed.", "error")
            return redirect(url_for("admin"))

        if user.is_admin:
            admins = db.session.scalars(select(User)).all()
            admin_count = sum(1 for u in admins if u.is_administrator)
            if admin_count <= 1:
                flash("Cannot remove the last admin.", "error")
                return redirect(url_for("admin"))
            user.is_admin = False
            db.session.commit()
            flash(f"{user.email} is no longer an admin.", "success")
        else:
            user.is_admin = True
            db.session.commit()
            flash(f"{user.email} is now an admin.", "success")

        return redirect(url_for("admin"))


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
