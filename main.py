"""PixelCoin — premium crypto banking platform."""

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import select

from models import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    CREDIT_INITIAL_LIMIT,
    WELCOME_BONUS,
    Card,
    CreditLine,
    CreditTransaction,
    Transfer,
    User,
    db,
)

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

    @app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    @admin_required
    def delete_user(user_id: int):
        user = db.session.get(User, user_id)
        if user is None:
            flash("User not found.", "error")
            return redirect(url_for("admin"))

        if user.id == current_user.id:
            flash("You cannot delete your own account.", "error")
            return redirect(url_for("admin"))

        if user.email.lower() == ADMIN_EMAIL.lower():
            flash("The primary admin account cannot be deleted.", "error")
            return redirect(url_for("admin"))

        if user.is_administrator:
            admins = db.session.scalars(select(User)).all()
            admin_count = sum(1 for u in admins if u.is_administrator)
            if admin_count <= 1:
                flash("Cannot delete the last admin.", "error")
                return redirect(url_for("admin"))

        email = user.email
        db.session.delete(user)
        db.session.commit()
        flash(f"User {email} has been deleted.", "success")
        return redirect(url_for("admin"))

    @app.route("/cards")
    @login_required
    def cards():
        card = current_user.card
        transfers = _user_transfers(current_user.id) if card else []
        return render_template("cards.html", card=card, transfers=transfers)

    @app.route("/cards/open", methods=["POST"])
    @login_required
    def open_card():
        if current_user.card:
            flash("You already have an active PixelCoin card.", "info")
            return redirect(url_for("cards"))

        card = Card(
            user_id=current_user.id,
            card_number=Card.generate_number(current_user.id),
            balance=WELCOME_BONUS,
        )
        db.session.add(card)
        db.session.commit()
        flash(f"Your PixelCoin card is ready! Welcome bonus: ${WELCOME_BONUS:,.2f}", "success")
        return redirect(url_for("cards"))

    @app.route("/cards/transfer", methods=["POST"])
    @login_required
    def transfer():
        card = current_user.card
        if card is None:
            flash("Open your PixelCoin card first.", "error")
            return redirect(url_for("cards"))

        recipient_email = request.form.get("recipient_email", "").strip().lower()
        amount_raw = request.form.get("amount", "").strip()

        try:
            amount = Decimal(amount_raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            flash("Enter a valid amount.", "error")
            return redirect(url_for("cards"))

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return redirect(url_for("cards"))

        if recipient_email == current_user.email.lower():
            flash("You cannot transfer money to yourself.", "error")
            return redirect(url_for("cards"))

        recipient = db.session.scalar(select(User).where(User.email == recipient_email))
        if recipient is None:
            flash("Recipient not found.", "error")
            return redirect(url_for("cards"))

        if recipient.card is None:
            flash("Recipient has not opened a PixelCoin card yet.", "error")
            return redirect(url_for("cards"))

        if card.balance < amount:
            flash("Insufficient balance.", "error")
            return redirect(url_for("cards"))

        card.balance -= amount
        recipient.card.balance += amount
        transfer_record = Transfer(
            sender_id=current_user.id,
            recipient_id=recipient.id,
            amount=amount,
        )
        db.session.add(transfer_record)
        db.session.commit()
        flash(f"Successfully sent ${amount:,.2f} to {recipient.email}.", "success")
        return redirect(url_for("cards"))

    @app.route("/admin/users/<int:user_id>/card")
    @admin_required
    def admin_user_card(user_id: int):
        user = db.session.get(User, user_id)
        if user is None:
            flash("User not found.", "error")
            return redirect(url_for("admin"))

        transfers = _user_transfers(user.id) if user.card else []
        return render_template("admin_user_card.html", user=user, transfers=transfers)

    @app.route("/savings")
    @login_required
    def savings():
        credit = current_user.credit_line
        transactions = []
        can_withdraw = False
        next_withdrawal = None

        if credit:
            transactions = db.session.scalars(
                select(CreditTransaction)
                .where(CreditTransaction.user_id == current_user.id)
                .order_by(CreditTransaction.created_at.desc())
            ).all()
            can_withdraw = _can_withdraw_credit(credit)
            if credit.last_withdrawal_at and not can_withdraw:
                last = _ensure_utc(credit.last_withdrawal_at)
                next_withdrawal = last + timedelta(days=30)
            _show_credit_reminder(credit)

        return render_template(
            "savings.html",
            credit=credit,
            transactions=transactions,
            can_withdraw=can_withdraw,
            next_withdrawal=next_withdrawal,
        )

    @app.route("/savings/open", methods=["POST"])
    @login_required
    def open_credit():
        if current_user.credit_line:
            flash("You already have an active PixelCoin credit line.", "info")
            return redirect(url_for("savings"))

        credit = CreditLine(
            user_id=current_user.id,
            card_number=CreditLine.generate_number(current_user.id),
            credit_limit=CREDIT_INITIAL_LIMIT,
            balance_used=Decimal("0.00"),
        )
        db.session.add(credit)
        db.session.commit()
        flash(
            f"Credit line opened! Your limit is ${CREDIT_INITIAL_LIMIT:,.0f}. "
            "You can withdraw funds once per month. Repay from your PixelCoin card.",
            "success",
        )
        return redirect(url_for("savings"))

    @app.route("/savings/withdraw", methods=["POST"])
    @login_required
    def credit_withdraw():
        credit = current_user.credit_line
        if credit is None:
            flash("Open your credit line first.", "error")
            return redirect(url_for("savings"))

        if current_user.card is None:
            flash("Open your PixelCoin card first to receive credit funds.", "error")
            return redirect(url_for("cards"))

        if not _can_withdraw_credit(credit):
            flash("You can withdraw credit funds once per month. Please wait until next month.", "error")
            return redirect(url_for("savings"))

        amount_raw = request.form.get("amount", "").strip()
        try:
            amount = Decimal(amount_raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            flash("Enter a valid amount.", "error")
            return redirect(url_for("savings"))

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return redirect(url_for("savings"))

        if amount > credit.available_credit:
            flash(f"Amount exceeds available credit (${credit.available_credit:,.2f}).", "error")
            return redirect(url_for("savings"))

        credit.balance_used += amount
        credit.last_withdrawal_at = datetime.now(timezone.utc)
        current_user.card.balance += amount
        db.session.add(CreditTransaction(user_id=current_user.id, amount=amount, transaction_type="withdraw"))
        db.session.commit()
        flash(
            f"${amount:,.2f} added to your card from credit. "
            "Remember to repay from your PixelCoin card balance.",
            "success",
        )
        return redirect(url_for("savings"))

    @app.route("/savings/pay", methods=["POST"])
    @login_required
    def credit_pay():
        credit = current_user.credit_line
        if credit is None or credit.balance_used <= 0:
            flash("No outstanding credit balance to pay.", "error")
            return redirect(url_for("savings"))

        if current_user.card is None:
            flash("Open your PixelCoin card to make a payment.", "error")
            return redirect(url_for("cards"))

        amount_raw = request.form.get("amount", "").strip()
        try:
            amount = Decimal(amount_raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            flash("Enter a valid amount.", "error")
            return redirect(url_for("savings"))

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return redirect(url_for("savings"))

        if amount > credit.balance_used:
            amount = credit.balance_used

        if current_user.card.balance < amount:
            flash("Insufficient balance on your PixelCoin card.", "error")
            return redirect(url_for("savings"))

        credit.balance_used -= amount
        current_user.card.balance -= amount
        db.session.add(CreditTransaction(user_id=current_user.id, amount=amount, transaction_type="payment"))
        db.session.commit()
        flash(f"Payment of ${amount:,.2f} applied to your credit line.", "success")
        return redirect(url_for("savings"))

    @app.route("/pxl")
    def pxl():
        return render_template("pxl.html")


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _can_withdraw_credit(credit: CreditLine) -> bool:
    if credit.last_withdrawal_at is None:
        return True
    last = _ensure_utc(credit.last_withdrawal_at)
    return datetime.now(timezone.utc) >= last + timedelta(days=30)


def _show_credit_reminder(credit: CreditLine) -> None:
    if credit.balance_used <= 0:
        return
    today = date.today()
    if credit.last_reminder_date != today:
        credit.last_reminder_date = today
        db.session.commit()
        flash(
            f"Reminder: You owe ${credit.balance_used:,.2f} on your credit line. "
            "Please send a payment from your PixelCoin card to reduce your balance.",
            "info",
        )


def _user_transfers(user_id: int) -> list:
    return db.session.scalars(
        select(Transfer)
        .where((Transfer.sender_id == user_id) | (Transfer.recipient_id == user_id))
        .order_by(Transfer.created_at.desc())
    ).all()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
