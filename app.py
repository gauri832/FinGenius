import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Setup SQLAlchemy
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "fingenius-dev-key")

# Configure the database
# Use DATABASE_URL environment variable, or fallback to a SQLite database for local testing
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///finance_app.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# Initialize the app with the extension
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Add datetime to all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Default categories
default_expense_categories = [
    "Housing", "Transportation", "Food", "Utilities", "Insurance", 
    "Healthcare", "Debt Payments", "Savings", "Personal", "Entertainment", 
    "Education", "Clothing", "Gifts/Donations", "Miscellaneous"
]

default_income_categories = [
    "Salary", "Freelance", "Business", "Investments", "Rental", 
    "Gifts", "Other"
]

# Helper functions
def is_authenticated():
    return current_user.is_authenticated

def get_user_data(user_id, data_type):
    from models import User, Expense, Income, Goal, Investment, Budget
    
    if data_type == 'expenses':
        return Expense.query.filter_by(user_id=user_id).all()
    elif data_type == 'incomes':
        return Income.query.filter_by(user_id=user_id).all()
    elif data_type == 'goals':
        return Goal.query.filter_by(user_id=user_id).all()
    elif data_type == 'investments':
        return Investment.query.filter_by(user_id=user_id).all()
    elif data_type == 'budgets':
        return Budget.query.filter_by(user_id=user_id).all()
    return []

# Routes
@app.route('/')
@login_required
def index():
    user_expenses = get_user_data(current_user.id, 'expenses')
    user_incomes = get_user_data(current_user.id, 'incomes')
    user_goals = get_user_data(current_user.id, 'goals')
    user_investments = get_user_data(current_user.id, 'investments')
    
    # Calculate financial summary
    total_expenses = sum(expense.amount for expense in user_expenses)
    total_income = sum(income.amount for income in user_incomes)
    net_worth = total_income - total_expenses
    
    # Get latest transactions
    latest_expenses = sorted(user_expenses, key=lambda x: x.date, reverse=True)[:5]
    latest_incomes = sorted(user_incomes, key=lambda x: x.date, reverse=True)[:5]
    
    return render_template('index.html', 
                          username=current_user.username,
                          total_expenses=total_expenses,
                          total_income=total_income,
                          net_worth=net_worth,
                          expenses=latest_expenses,
                          incomes=latest_incomes,
                          goals=user_goals,
                          investments=user_investments)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Find user by username
        from models import User
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            # Store username in session for easy access in templates
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        from models import User
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        # Check if email already exists
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Initialize default budgets
        from models import Budget
        for category in default_expense_categories:
            budget = Budget(category=category, amount=0, user_id=new_user.id)
            db.session.add(budget)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    # Clear Flask-Login's session
    logout_user()
    # Clear any additional items we stored in session
    session.pop('username', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expense_tracker():
    from models import Expense
    user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        # Add new expense
        description = request.form.get('description')
        amount = float(request.form.get('amount'))
        category = request.form.get('category')
        date_str = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        new_expense = Expense(
            description=description,
            amount=amount,
            category=category,
            date=expense_date,
            user_id=current_user.id
        )
        
        db.session.add(new_expense)
        db.session.commit()
        
        flash('Expense added successfully!', 'success')
        return redirect(url_for('expense_tracker'))
    
    return render_template('expenses.html', 
                          expenses=user_expenses, 
                          categories=default_expense_categories)

@app.route('/api/expenses', methods=['GET'])
@login_required
def get_expenses():
    from models import Expense
    user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    
    # Convert SQLAlchemy objects to dictionaries
    expenses_list = []
    for expense in user_expenses:
        expenses_list.append({
            'id': expense.id,
            'description': expense.description,
            'amount': expense.amount,
            'category': expense.category,
            'date': expense.date.strftime('%Y-%m-%d')
        })
    
    return jsonify(expenses_list)

@app.route('/api/expenses', methods=['POST'])
@login_required
def add_expense():
    from models import Expense
    data = request.json
    
    description = data.get('description')
    amount = float(data.get('amount'))
    category = data.get('category')
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    new_expense = Expense(
        description=description,
        amount=amount,
        category=category,
        date=expense_date,
        user_id=current_user.id
    )
    
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'expense': {
            'id': new_expense.id,
            'description': new_expense.description,
            'amount': new_expense.amount,
            'category': new_expense.category,
            'date': new_expense.date.strftime('%Y-%m-%d')
        }
    })

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    from models import Expense
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
    
    if expense:
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'Expense not found'}), 404

@app.route('/income', methods=['GET', 'POST'])
@login_required
def income_tracker():
    from models import Income
    user_incomes = Income.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        # Add new income
        description = request.form.get('description')
        amount = float(request.form.get('amount'))
        category = request.form.get('category')
        date_str = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        income_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        new_income = Income(
            description=description,
            amount=amount,
            category=category,
            date=income_date,
            user_id=current_user.id
        )
        
        db.session.add(new_income)
        db.session.commit()
        
        flash('Income added successfully!', 'success')
        return redirect(url_for('income_tracker'))
    
    return render_template('income.html', 
                          incomes=user_incomes, 
                          categories=default_income_categories)

@app.route('/api/incomes', methods=['GET'])
@login_required
def get_incomes():
    from models import Income
    user_incomes = Income.query.filter_by(user_id=current_user.id).all()
    
    # Convert SQLAlchemy objects to dictionaries
    incomes_list = []
    for income in user_incomes:
        incomes_list.append({
            'id': income.id,
            'description': income.description,
            'amount': income.amount,
            'category': income.category,
            'date': income.date.strftime('%Y-%m-%d')
        })
    
    return jsonify(incomes_list)

@app.route('/api/incomes', methods=['POST'])
@login_required
def add_income():
    from models import Income
    data = request.json
    
    description = data.get('description')
    amount = float(data.get('amount'))
    category = data.get('category')
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    income_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    new_income = Income(
        description=description,
        amount=amount,
        category=category,
        date=income_date,
        user_id=current_user.id
    )
    
    db.session.add(new_income)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'income': {
            'id': new_income.id,
            'description': new_income.description,
            'amount': new_income.amount,
            'category': new_income.category,
            'date': new_income.date.strftime('%Y-%m-%d')
        }
    })

@app.route('/api/incomes/<int:income_id>', methods=['DELETE'])
@login_required
def delete_income(income_id):
    from models import Income
    income = Income.query.filter_by(id=income_id, user_id=current_user.id).first()
    
    if income:
        db.session.delete(income)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'Income not found'}), 404

@app.route('/goals', methods=['GET', 'POST'])
@login_required
def goal_tracker():
    from models import Goal
    user_goals = Goal.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        # Add new goal
        name = request.form.get('name')
        target_amount = float(request.form.get('target_amount'))
        current_amount = float(request.form.get('current_amount', 0))
        target_date_str = request.form.get('target_date')
        description = request.form.get('description', '')
        
        # Parse date if provided
        target_date = None
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        
        new_goal = Goal(
            name=name,
            target_amount=target_amount,
            current_amount=current_amount,
            target_date=target_date,
            description=description,
            user_id=current_user.id
        )
        
        db.session.add(new_goal)
        db.session.commit()
        
        flash('Goal added successfully!', 'success')
        return redirect(url_for('goal_tracker'))
    
    return render_template('goals.html', goals=user_goals)

@app.route('/api/goals', methods=['GET'])
@login_required
def get_goals():
    from models import Goal
    user_goals = Goal.query.filter_by(user_id=current_user.id).all()
    
    # Convert SQLAlchemy objects to dictionaries
    goals_list = []
    for goal in user_goals:
        goals_list.append({
            'id': goal.id,
            'name': goal.name,
            'target_amount': goal.target_amount,
            'current_amount': goal.current_amount,
            'target_date': goal.target_date.strftime('%Y-%m-%d') if goal.target_date else None,
            'description': goal.description
        })
    
    return jsonify(goals_list)

@app.route('/api/goals', methods=['POST'])
@login_required
def add_goal():
    from models import Goal
    data = request.json
    
    name = data.get('name')
    target_amount = float(data.get('target_amount'))
    current_amount = float(data.get('current_amount', 0))
    target_date_str = data.get('target_date')
    description = data.get('description', '')
    
    # Parse date if provided
    target_date = None
    if target_date_str:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    
    new_goal = Goal(
        name=name,
        target_amount=target_amount,
        current_amount=current_amount,
        target_date=target_date,
        description=description,
        user_id=current_user.id
    )
    
    db.session.add(new_goal)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'goal': {
            'id': new_goal.id,
            'name': new_goal.name,
            'target_amount': new_goal.target_amount,
            'current_amount': new_goal.current_amount,
            'target_date': new_goal.target_date.strftime('%Y-%m-%d') if new_goal.target_date else None,
            'description': new_goal.description
        }
    })

@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
@login_required
def update_goal(goal_id):
    from models import Goal
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first()
    
    if goal:
        data = request.json
        
        if 'name' in data:
            goal.name = data.get('name')
        if 'target_amount' in data:
            goal.target_amount = float(data.get('target_amount'))
        if 'current_amount' in data:
            goal.current_amount = float(data.get('current_amount'))
        if 'target_date' in data:
            target_date_str = data.get('target_date')
            goal.target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date() if target_date_str else None
        if 'description' in data:
            goal.description = data.get('description')
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'goal': {
                'id': goal.id,
                'name': goal.name,
                'target_amount': goal.target_amount,
                'current_amount': goal.current_amount,
                'target_date': goal.target_date.strftime('%Y-%m-%d') if goal.target_date else None,
                'description': goal.description
            }
        })
    
    return jsonify({'error': 'Goal not found'}), 404

@app.route('/api/goals/<int:goal_id>', methods=['DELETE'])
@login_required
def delete_goal(goal_id):
    from models import Goal
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first()
    
    if goal:
        db.session.delete(goal)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'Goal not found'}), 404

@app.route('/investments', methods=['GET', 'POST'])
@login_required
def investment_tracker():
    from models import Investment
    user_investments = Investment.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        # Add new investment
        name = request.form.get('name')
        type = request.form.get('type')
        amount = float(request.form.get('amount'))
        purchase_date_str = request.form.get('purchase_date')
        purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
        current_value = float(request.form.get('current_value', amount))
        notes = request.form.get('notes', '')
        
        new_investment = Investment(
            name=name,
            type=type,
            amount=amount,
            purchase_date=purchase_date,
            current_value=current_value,
            notes=notes,
            user_id=current_user.id
        )
        
        db.session.add(new_investment)
        db.session.commit()
        
        flash('Investment added successfully!', 'success')
        return redirect(url_for('investment_tracker'))
    
    investment_types = [
        "Stocks", "Bonds", "Mutual Funds", "ETFs", "Real Estate", 
        "Retirement Accounts", "Cryptocurrencies", "Other"
    ]
    
    return render_template('investments.html', 
                          investments=user_investments,
                          investment_types=investment_types)

@app.route('/api/investments', methods=['GET'])
@login_required
def get_investments():
    from models import Investment
    user_investments = Investment.query.filter_by(user_id=current_user.id).all()
    
    # Convert SQLAlchemy objects to dictionaries
    investments_list = []
    for investment in user_investments:
        investments_list.append({
            'id': investment.id,
            'name': investment.name,
            'type': investment.type,
            'amount': investment.amount,
            'purchase_date': investment.purchase_date.strftime('%Y-%m-%d'),
            'current_value': investment.current_value,
            'notes': investment.notes
        })
    
    return jsonify(investments_list)

@app.route('/api/investments', methods=['POST'])
@login_required
def add_investment():
    from models import Investment
    data = request.json
    
    name = data.get('name')
    type = data.get('type')
    amount = float(data.get('amount'))
    purchase_date_str = data.get('purchase_date')
    purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
    current_value = float(data.get('current_value', amount))
    notes = data.get('notes', '')
    
    new_investment = Investment(
        name=name,
        type=type,
        amount=amount,
        purchase_date=purchase_date,
        current_value=current_value,
        notes=notes,
        user_id=current_user.id
    )
    
    db.session.add(new_investment)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'investment': {
            'id': new_investment.id,
            'name': new_investment.name,
            'type': new_investment.type,
            'amount': new_investment.amount,
            'purchase_date': new_investment.purchase_date.strftime('%Y-%m-%d'),
            'current_value': new_investment.current_value,
            'notes': new_investment.notes
        }
    })

@app.route('/api/investments/<int:investment_id>', methods=['PUT'])
@login_required
def update_investment(investment_id):
    from models import Investment
    investment = Investment.query.filter_by(id=investment_id, user_id=current_user.id).first()
    
    if investment:
        data = request.json
        
        if 'name' in data:
            investment.name = data.get('name')
        if 'type' in data:
            investment.type = data.get('type')
        if 'amount' in data:
            investment.amount = float(data.get('amount'))
        if 'purchase_date' in data:
            purchase_date_str = data.get('purchase_date')
            investment.purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
        if 'current_value' in data:
            investment.current_value = float(data.get('current_value'))
        if 'notes' in data:
            investment.notes = data.get('notes')
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'investment': {
                'id': investment.id,
                'name': investment.name,
                'type': investment.type,
                'amount': investment.amount,
                'purchase_date': investment.purchase_date.strftime('%Y-%m-%d'),
                'current_value': investment.current_value,
                'notes': investment.notes
            }
        })
    
    return jsonify({'error': 'Investment not found'}), 404

@app.route('/api/investments/<int:investment_id>', methods=['DELETE'])
@login_required
def delete_investment(investment_id):
    from models import Investment
    investment = Investment.query.filter_by(id=investment_id, user_id=current_user.id).first()
    
    if investment:
        db.session.delete(investment)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'Investment not found'}), 404

@app.route('/suggestions')
@login_required
def suggestions():
    from models import Expense, Income, Goal, Investment
    
    user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    user_incomes = Income.query.filter_by(user_id=current_user.id).all()
    user_goals = Goal.query.filter_by(user_id=current_user.id).all()
    user_investments = Investment.query.filter_by(user_id=current_user.id).all()
    
    # Calculate financial suggestions
    total_expenses = sum(expense.amount for expense in user_expenses)
    total_income = sum(income.amount for income in user_incomes)
    net_worth = total_income - total_expenses
    
    # Group expenses by category
    expense_by_category = {}
    for expense in user_expenses:
        category = expense.category
        if category not in expense_by_category:
            expense_by_category[category] = 0
        expense_by_category[category] += expense.amount
    
    # Generate suggestions
    suggestions = []
    
    # Income/Expense ratio suggestion
    if total_income > 0:
        expense_ratio = total_expenses / total_income
        if expense_ratio > 0.9:
            suggestions.append({
                'title': 'Reduce Expenses',
                'description': 'Your expenses are {:.1f}% of your income. Aim to keep expenses below 70% of income.'.format(expense_ratio * 100),
                'type': 'warning'
            })
        elif expense_ratio < 0.5:
            suggestions.append({
                'title': 'Great Savings Rate',
                'description': 'You\'re saving {:.1f}% of your income. Consider investing more for long-term growth.'.format((1-expense_ratio) * 100),
                'type': 'success'
            })
    
    # Emergency fund suggestion
    if not user_investments:
        suggestions.append({
            'title': 'Start an Emergency Fund',
            'description': 'Consider building an emergency fund with 3-6 months of expenses.',
            'type': 'info'
        })
    
    # Investment diversification suggestion
    investment_types = set(inv.type for inv in user_investments)
    if len(investment_types) < 3 and user_investments:
        suggestions.append({
            'title': 'Diversify Investments',
            'description': 'Consider diversifying your investment portfolio across different asset classes.',
            'type': 'info'
        })
    
    # High expense category suggestion
    if expense_by_category:
        highest_category = max(expense_by_category.items(), key=lambda x: x[1])
        if highest_category[1] > (total_expenses * 0.4):  # If one category is over 40% of total
            suggestions.append({
                'title': 'High {} Expenses'.format(highest_category[0]),
                'description': '{} expenses make up {:.1f}% of your total spending. Consider ways to reduce this.'.format(
                    highest_category[0], (highest_category[1] / total_expenses) * 100),
                'type': 'warning'
            })
    
    # Goal progress suggestion
    for goal in user_goals:
        target = goal.target_amount
        current = goal.current_amount
        progress = (current / target) if target > 0 else 0
        
        if progress < 0.25:
            suggestions.append({
                'title': 'Goal: {}'.format(goal.name),
                'description': 'You\'re only {:.1f}% of the way to your goal. Consider allocating more funds.'.format(progress * 100),
                'type': 'warning'
            })
            
    # Default suggestions if we don't have enough data yet
    if not suggestions:
        suggestions = [
            {
                'title': 'Track Your Expenses',
                'description': 'Start by logging all your expenses to get better financial insights.',
                'type': 'info'
            },
            {
                'title': 'Set Financial Goals',
                'description': 'Define clear financial goals to help motivate your saving and investing habits.',
                'type': 'info'
            },
            {
                'title': 'Create a Budget',
                'description': 'A budget is the foundation of financial success. Use our budget tool to get started.',
                'type': 'info'
            }
        ]
    
    return render_template('suggestions.html', suggestions=suggestions)

@app.route('/budget', methods=['GET', 'POST'])
@login_required
def budget_planner():
    from models import Budget, Expense
    user_budgets = Budget.query.filter_by(user_id=current_user.id).all()
    user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    
    # Convert to a dictionary for easier access
    budget_dict = {budget.category: budget.amount for budget in user_budgets}
    
    # Ensure we have budget entries for all categories
    for category in default_expense_categories:
        if category not in budget_dict:
            new_budget = Budget(
                category=category,
                amount=0,
                user_id=current_user.id
            )
            db.session.add(new_budget)
            budget_dict[category] = 0
    
    if len(budget_dict) != len(default_expense_categories):
        db.session.commit()
    
    if request.method == 'POST':
        # Update budget limits
        for category in default_expense_categories:
            amount_str = request.form.get(f'budget_{category}', '0')
            amount = float(amount_str) if amount_str and amount_str.strip() else 0
            
            # Find existing budget or create new one
            budget = Budget.query.filter_by(category=category, user_id=current_user.id).first()
            if budget:
                budget.amount = amount
            else:
                new_budget = Budget(
                    category=category,
                    amount=amount,
                    user_id=current_user.id
                )
                db.session.add(new_budget)
        
        db.session.commit()
        flash('Budget updated successfully!', 'success')
        return redirect(url_for('budget_planner'))
    
    # Calculate current spending by category
    spending_by_category = {category: 0 for category in default_expense_categories}
    for expense in user_expenses:
        category = expense.category
        if category in spending_by_category:
            spending_by_category[category] += expense.amount
    
    # Prepare data for the template
    budget_data = []
    for category in default_expense_categories:
        budget_amount = budget_dict.get(category, 0)
        spent_amount = spending_by_category.get(category, 0)
        percentage = (spent_amount / budget_amount * 100) if budget_amount > 0 else 0
        
        budget_data.append({
            'category': category,
            'budget_amount': budget_amount,
            'spent_amount': spent_amount,
            'percentage': min(percentage, 100),  # Cap at 100% for visual display
            'status': 'danger' if percentage > 100 else 'warning' if percentage > 70 else 'success'
        })
    
    return render_template('budget.html', 
                          budget_data=budget_data,
                          categories=default_expense_categories)

@app.route('/api/budget', methods=['GET'])
@login_required
def get_budget():
    from models import Budget
    user_budgets = Budget.query.filter_by(user_id=current_user.id).all()
    
    # Convert to a dictionary for the API response
    budget_dict = {}
    for budget in user_budgets:
        budget_dict[budget.category] = budget.amount
    
    return jsonify(budget_dict)

@app.route('/api/budget', methods=['POST'])
@login_required
def update_budget():
    from models import Budget
    data = request.json
    
    for category, amount in data.items():
        # Find existing budget or create new one
        budget = Budget.query.filter_by(category=category, user_id=current_user.id).first()
        if budget:
            budget.amount = float(amount)
        else:
            new_budget = Budget(
                category=category,
                amount=float(amount),
                user_id=current_user.id
            )
            db.session.add(new_budget)
    
    db.session.commit()
    
    # Return the updated budget
    return jsonify({'success': True})

@app.route('/api/summary', methods=['GET'])
@login_required
def get_financial_summary():
    from models import Expense, Income, Investment
    
    user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    user_incomes = Income.query.filter_by(user_id=current_user.id).all()
    user_investments = Investment.query.filter_by(user_id=current_user.id).all()
    
    # Calculate totals
    total_expenses = sum(expense.amount for expense in user_expenses)
    total_income = sum(income.amount for income in user_incomes)
    total_investments = sum(investment.current_value for investment in user_investments)
    net_worth = total_income - total_expenses + total_investments
    
    # Group expenses by category
    expense_by_category = {}
    for expense in user_expenses:
        category = expense.category
        if category not in expense_by_category:
            expense_by_category[category] = 0
        expense_by_category[category] += expense.amount
    
    # Group income by category
    income_by_category = {}
    for income in user_incomes:
        category = income.category
        if category not in income_by_category:
            income_by_category[category] = 0
        income_by_category[category] += income.amount
    
    # Group investments by type
    investments_by_type = {}
    for investment in user_investments:
        inv_type = investment.type
        if inv_type not in investments_by_type:
            investments_by_type[inv_type] = 0
        investments_by_type[inv_type] += investment.current_value
    
    return jsonify({
        'total_expenses': total_expenses,
        'total_income': total_income,
        'total_investments': total_investments,
        'net_worth': net_worth,
        'expense_by_category': expense_by_category,
        'income_by_category': income_by_category,
        'investments_by_type': investments_by_type
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
