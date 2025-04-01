from app import db
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    
    expenses = db.relationship('Expense', backref='user', lazy='dynamic')
    incomes = db.relationship('Income', backref='user', lazy='dynamic')
    goals = db.relationship('Goal', backref='user', lazy='dynamic')
    investments = db.relationship('Investment', backref='user', lazy='dynamic')
    budgets = db.relationship('Budget', backref='user', lazy='dynamic')


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(128), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(64), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.now().date())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(128), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(64), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.now().date())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0)
    target_date = db.Column(db.Date)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    type = db.Column(db.String(64), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    current_value = db.Column(db.Float)
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(64), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
