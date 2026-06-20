import secrets
from datetime import datetime, timezone
from decimal import Decimal

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ADMIN_EMAIL = "admin123@gmail.com"
ADMIN_PASSWORD = "1234"
WELCOME_BONUS = Decimal("1000.00")
CREDIT_INITIAL_LIMIT = Decimal("100000.00")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    card = db.relationship("Card", back_populates="user", uselist=False, cascade="all, delete-orphan")
    transfers_sent = db.relationship(
        "Transfer",
        foreign_keys="Transfer.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )
    transfers_received = db.relationship(
        "Transfer",
        foreign_keys="Transfer.recipient_id",
        back_populates="recipient",
        cascade="all, delete-orphan",
    )
    credit_line = db.relationship(
        "CreditLine", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    credit_transactions = db.relationship(
        "CreditTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_administrator(self) -> bool:
        return self.is_admin or self.email.lower() == ADMIN_EMAIL.lower()


class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    card_number = db.Column(db.String(19), unique=True, nullable=False)
    balance = db.Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    opened_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="card")

    @staticmethod
    def generate_number(user_id: int) -> str:
        suffix = secrets.randbelow(10_000_000_000)
        return f"4532 {user_id:04d} {suffix // 10000:04d} {suffix % 10000:04d}"


class Transfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="transfers_sent")
    recipient = db.relationship("User", foreign_keys=[recipient_id], back_populates="transfers_received")


class CreditLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    card_number = db.Column(db.String(19), unique=True, nullable=False)
    credit_limit = db.Column(Numeric(12, 2), default=CREDIT_INITIAL_LIMIT, nullable=False)
    balance_used = db.Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    opened_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_withdrawal_at = db.Column(db.DateTime, nullable=True)
    last_reminder_date = db.Column(db.Date, nullable=True)

    user = db.relationship("User", back_populates="credit_line")

    @property
    def available_credit(self) -> Decimal:
        return self.credit_limit - self.balance_used

    @staticmethod
    def generate_number(user_id: int) -> str:
        suffix = secrets.randbelow(10_000_000_000)
        return f"5528 {user_id:04d} {suffix // 10000:04d} {suffix % 10000:04d}"


class CreditTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(Numeric(12, 2), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # withdraw, payment
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="credit_transactions")
