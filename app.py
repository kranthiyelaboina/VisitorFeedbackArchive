from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask import session, send_file, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import csv
import io
import json
from functools import wraps
import secrets
import pandas as pd
from sqlalchemy import or_
import re
from textblob import TextBlob  # For sentiment analysis

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///feedback.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Define models
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'category': self.category,
            'message': self.message,
            'sentiment': self.sentiment,
            'submitted_at': self.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Create database tables
with app.app_context():
    db.create_all()
    # Create default admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

# Predefined categories
CATEGORIES = [
    'General Feedback', 
    'Bug Report', 
    'Feature Request', 
    'Complaint', 
    'Compliment', 
    'Question'
]

# Admin login required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function for sentiment analysis
def analyze_sentiment(text):
    analysis = TextBlob(text)
    # Determine sentiment based on polarity
    if analysis.sentiment.polarity > 0.1:
        return "Positive"
    elif analysis.sentiment.polarity < -0.1:
        return "Negative"
    else:
        return "Neutral"

# Routes
@app.route('/')
def index():
    return render_template_string(INDEX_TEMPLATE)

@app.route('/submit', methods=['POST'])
def submit_feedback():
    name = request.form.get('name')
    email = request.form.get('email')
    category = request.form.get('category')
    message = request.form.get('message')
    
    # Basic validation
    if not name or not category or not message:
        flash('Please fill in all required fields', 'danger')
        return redirect(url_for('index'))
    
    # Email validation if provided
    if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash('Please enter a valid email address', 'danger')
        return redirect(url_for('index'))
    
    # Analyze sentiment
    sentiment = analyze_sentiment(message)
    
    # Create new feedback
    new_feedback = Feedback(
        name=name,
        email=email,
        category=category,
        message=message,
        sentiment=sentiment
    )
    
    db.session.add(new_feedback)
    db.session.commit()
    
    flash('Thank you for your feedback!', 'success')
    return redirect(url_for('index'))

@app.route('/archive')
def archive():
    category = request.args.get('category', '')
    date_start = request.args.get('date_start', '')
    date_end = request.args.get('date_end', '')
    search_query = request.args.get('search', '')
    
    # Base query
    query = Feedback.query
    
    # Apply filters
    if category and category != 'All':
        query = query.filter_by(category=category)
    
    if date_start:
        query = query.filter(Feedback.submitted_at >= datetime.strptime(date_start, '%Y-%m-%d'))
    
    if date_end:
        query = query.filter(Feedback.submitted_at <= datetime.strptime(date_end + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    
    if search_query:
        query = query.filter(or_(
            Feedback.name.contains(search_query),
            Feedback.message.contains(search_query),
            Feedback.email.contains(search_query)
        ))
    
    # Get all feedback sorted by newest first
    feedback_list = query.order_by(Feedback.submitted_at.desc()).all()
    
    # Check if user is logged in as admin
    is_admin = 'logged_in' in session
    
    return render_template_string(
        ARCHIVE_TEMPLATE, 
        feedback_list=feedback_list, 
        categories=CATEGORIES,
        current_category=category,
        date_start=date_start,
        date_end=date_end,
        search_query=search_query,
        is_admin=is_admin
    )

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template_string(ADMIN_LOGIN_TEMPLATE)

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    feedback_list = Feedback.query.order_by(Feedback.submitted_at.desc()).all()
    return render_template_string(
        ADMIN_DASHBOARD_TEMPLATE, 
        feedback_list=feedback_list,
        categories=CATEGORIES
    )

@app.route('/admin/delete/<int:feedback_id>', methods=['POST'])
@admin_required
def delete_feedback(feedback_id):
    feedback = Feedback.query.get_or_404(feedback_id)
    db.session.delete(feedback)
    db.session.commit()
    flash('Feedback deleted successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/archive/delete/<int:feedback_id>', methods=['POST'])
@admin_required
def delete_feedback_from_archive(feedback_id):
    feedback = Feedback.query.get_or_404(feedback_id)
    db.session.delete(feedback)
    db.session.commit()
    flash('Feedback deleted successfully', 'success')
    
    # Preserve the existing filter parameters
    return redirect(url_for('archive', 
                          category=request.args.get('category', ''),
                          date_start=request.args.get('date_start', ''),
                          date_end=request.args.get('date_end', ''),
                          search=request.args.get('search', '')))

@app.route('/export/<format>')
@admin_required
def export_feedback(format):
    feedback_list = Feedback.query.order_by(Feedback.submitted_at.desc()).all()
    
    if format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['ID', 'Name', 'Email', 'Category', 'Message', 'Sentiment', 'Submitted At'])
        
        # Write data
        for feedback in feedback_list:
            writer.writerow([
                feedback.id,
                feedback.name,
                feedback.email,
                feedback.category,
                feedback.message,
                feedback.sentiment,
                feedback.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='feedback_export.csv'
        )
    
    elif format == 'pdf':
        # Create a DataFrame and export as PDF
        data = []
        for feedback in feedback_list:
            data.append(feedback.to_dict())
        
        df = pd.DataFrame(data)
        
        # Use pandas to create an HTML table
        html_table = df.to_html(classes='table table-striped')
        
        # Render a template with the HTML table
        pdf_content = render_template_string(PDF_EXPORT_TEMPLATE, table=html_table)
        
        # Return the PDF content as a response
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=feedback_export.pdf'
        
        return response
    
    else:
        flash('Invalid export format', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/api/feedback', methods=['GET'])
def api_get_feedback():
    feedback_list = Feedback.query.order_by(Feedback.submitted_at.desc()).all()
    return jsonify([feedback.to_dict() for feedback in feedback_list])

# Template strings
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visitor Feedback System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #4e73df;
            --secondary-color: #6c757d;
            --success-color: #1cc88a;
            --info-color: #36b9cc;
            --warning-color: #f6c23e;
            --danger-color: #e74a3b;
            --light-color: #f8f9fc;
            --dark-color: #5a5c69;
        }
        
        body {
            font-family: 'Nunito', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f8f9fc;
            color: #5a5c69;
        }
        
        .navbar {
            background-color: white;
            box-shadow: 0 .15rem 1.75rem 0 rgba(58,59,69,.15);
        }
        
        .navbar-brand {
            font-weight: 700;
            color: var(--primary-color);
        }
        
        .card {
            border: none;
            box-shadow: 0 .15rem 1.75rem 0 rgba(58,59,69,.15);
            margin-bottom: 30px;
        }
        
        .card-header {
            background-color: #f8f9fc;
            border-bottom: 1px solid #e3e6f0;
            font-weight: 700;
            color: var(--primary-color);
        }
        
        .btn-primary {
            background-color: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .btn-primary:hover {
            background-color: #2e59d9;
            border-color: #2653d4;
        }
        
        footer {
            background-color: white;
            border-top: 1px solid #e3e6f0;
            padding: 15px 0;
        }
        
        .form-control:focus {
            border-color: #bac8f3;
            box-shadow: 0 0 0 0.25rem rgba(78, 115, 223, 0.25);
        }
        
        .hero-section {
            background: linear-gradient(135deg, #4e73df 0%, #224abe 100%);
            color: white;
            padding: 60px 0;
            margin-bottom: 30px;
        }
        
        .feature-icon {
            font-size: 2rem;
            margin-bottom: 1rem;
            color: var(--primary-color);
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">
                <i class="fas fa-comments me-2"></i>Feedback Archive
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link active" href="{{ url_for('index') }}">Submit Feedback</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('archive') }}">View Archive</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('admin_login') }}">Admin</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    
    <div class="hero-section">
        <div class="container text-center">
            <h1>We Value Your Feedback</h1>
            <p class="lead">Help us improve by sharing your thoughts, suggestions, and experiences</p>
        </div>
    </div>
    
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="row">
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-edit me-2"></i>Submit Your Feedback
                    </div>
                    <div class="card-body">
                        <form action="{{ url_for('submit_feedback') }}" method="post" id="feedbackForm">
                            <div class="mb-3">
                                <label for="name" class="form-label">Full Name <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="name" name="name" required>
                            </div>
                            
                            <div class="mb-3">
                                <label for="email" class="form-label">Email Address <span class="text-muted">(optional)</span></label>
                                <input type="email" class="form-control" id="email" name="email">
                                <div class="form-text">We'll never share your email with anyone else.</div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="category" class="form-label">Feedback Category <span class="text-danger">*</span></label>
                                <select class="form-select" id="category" name="category" required>
                                    <option value="" selected disabled>Select a category...</option>
                                    {% for category in ['General Feedback', 'Bug Report', 'Feature Request', 'Complaint', 'Compliment', 'Question'] %}
                                        <option value="{{ category }}">{{ category }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label for="message" class="form-label">Your Message <span class="text-danger">*</span></label>
                                <textarea class="form-control" id="message" name="message" rows="5" required></textarea>
                                <div class="form-text">Please provide as much detail as possible.</div>
                            </div>
                            
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-paper-plane me-2"></i>Submit Feedback
                            </button>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-info-circle me-2"></i>Why Your Feedback Matters
                    </div>
                    <div class="card-body">
                        <div class="mb-4 text-center">
                            <i class="fas fa-lightbulb feature-icon"></i>
                            <h5>Continuous Improvement</h5>
                            <p>Your feedback helps us identify areas where we can improve our services.</p>
                        </div>
                        
                        <div class="mb-4 text-center">
                            <i class="fas fa-users feature-icon"></i>
                            <h5>Community-Driven</h5>
                            <p>We value community input and use it to shape our future initiatives.</p>
                        </div>
                        
                        <div class="text-center">
                            <i class="fas fa-chart-line feature-icon"></i>
                            <h5>Measurement & Analytics</h5>
                            <p>Your insights help us measure our performance and make data-driven decisions.</p>
                        </div>
                        
                        <div class="mt-4 text-center">
                            <a href="{{ url_for('archive') }}" class="btn btn-outline-primary">
                                <i class="fas fa-archive me-2"></i>View Feedback Archive
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <footer class="mt-5">
        <div class="container text-center">
            <p class="mb-0">&copy; 2025 Visitor Feedback Archive. All rights reserved.</p>
        </div>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Client-side validation
        document.getElementById('feedbackForm').addEventListener('submit', function(event) {
            let valid = true;
            const name = document.getElementById('name').value.trim();
            const email = document.getElementById('email').value.trim();
            const category = document.getElementById('category').value;
            const message = document.getElementById('message').value.trim();
            
            if (!name) {
                valid = false;
                alert('Please enter your name');
            }
            
            if (email && !validateEmail(email)) {
                valid = false;
                alert('Please enter a valid email address');
            }
            
            if (!category) {
                valid = false;
                alert('Please select a category');
            }
            
            if (!message) {
                valid = false;
                alert('Please enter your message');
            }
            
            if (!valid) {
                event.preventDefault();
            }
        });
        
        function validateEmail(email) {
            const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return re.test(email);
        }
    </script>
</body>
</html>
'''

ARCHIVE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Feedback Archive</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #4e73df;
            --secondary-color: #6c757d;
            --success-color: #1cc88a;
            --info-color: #36b9cc;
            --warning-color: #f6c23e;
            --danger-color: #e74a3b;
            --light-color: #f8f9fc;
            --dark-color: #5a5c69;
        }
        
        body {
            font-family: 'Nunito', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f8f9fc;
            color: #5a5c69;
        }
        
        .navbar {
            background-color: white;
            box-shadow: 0 .15rem 1.75rem 0 rgba(58,59,69,.15);
        }
        
        .navbar-brand {
            font-weight: 700;
            color: var(--primary-color);
        }
        
        .card {
            border: none;
            box-shadow: 0 .15rem 1.75rem 0 rgba(58,59,69,.15);
            margin-bottom: 30px;
        }
        
        .card-header {
            background-color: #f8f9fc;
            border-bottom: 1px solid #e3e6f0;
            font-weight: 700;
            color: var(--primary-color);
        }
        
        .btn-primary {
            background-color: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .btn-primary:hover {
            background-color: #2e59d9;
            border-color: #2653d4;
        }
        
        footer {
            background-color: white;
            border-top: 1px solid #e3e6f0;
            padding: 15px 0;
        }
        
        .form-control:focus {
            border-color: #bac8f3;
            box-shadow: 0 0 0 0.25rem rgba(78, 115, 223, 0.25);
        }
        
        .page-header {
            background: linear-gradient(135deg, #4e73df 0%, #224abe 100%);
            color: white;
            padding: 30px 0;
            margin-bottom: 30px;
        }
        
        .feedback-item {
            transition: transform 0.3s ease;
        }
        
        .feedback-item:hover {
            transform: translateY(-5px);
        }
        
        .feedback-meta {
            font-size: 0.85rem;
            color: #858796;
        }
        
        .sentiment-positive {
            color: var(--success-color);
        }
        
        .sentiment-negative {
            color: var(--danger-color);
        }
        
        .sentiment-neutral {
            color: var(--info-color);
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">
                <i class="fas fa-comments me-2"></i>Feedback Archive
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('index') }}">Submit Feedback</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="{{ url_for('archive') }}">View Archive</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('admin_login') }}">Admin</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    
    <div class="page-header">
        <div class="container">
            <h1><i class="fas fa-archive me-2"></i>Feedback Archive</h1>
            <p class="lead">Browse and search through our collection of visitor feedback</p>
        </div>
    </div>
    
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="card mb-4">
            <div class="card-header">
                <i class="fas fa-filter me-2"></i>Filter Feedback
            </div>
            <div class="card-body">
                <form action="{{ url_for('archive') }}" method="get" id="filterForm">
                    <div class="row">
                        <div class="col-md-3 mb-3">
                            <label for="category" class="form-label">Category</label>
                            <select class="form-select" id="category" name="category">
                                <option value="All" {% if current_category == 'All' or not current_category %}selected{% endif %}>All Categories</option>
                                {% for category in categories %}
                                    <option value="{{ category }}" {% if current_category == category %}selected{% endif %}>{{ category }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="col-md-3 mb-3">
                            <label for="date_start" class="form-label">From Date</label>
                            <input type="date" class="form-control" id="date_start" name="date_start" value="{{ date_start }}">
                        </div>
                        
                        <div class="col-md-3 mb-3">
                            <label for="date_end" class="form-label">To Date</label>
                            <input type="date" class="form-control" id="date_end" name="date_end" value="{{ date_end }}">
                        </div>
                        
                        <div class="col-md-3 mb-3">
                            <label for="search" class="form-label">Search</label>
                            <div class="input-group">
                                <input type="text" class="form-control" id="search" name="search" value="{{ search_query }}" placeholder="Search...">
                                <button class="btn btn-primary" type="submit">
                                    <i class="fas fa-search"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </form>
            </div>
        </div>
        
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <div>
                            <i class="fas fa-list me-2"></i>Feedback Results
                            <span class="badge bg-primary ms-2">{{ feedback_list|length }}</span>
                        </div>
                        {% if is_admin %}
                        <div>
                            <span class="badge bg-info">Admin Mode</span>
                        </div>
                        {% endif %}
                    </div>
                    <div class="card-body">
                        {% if feedback_list %}
                            <div class="row">
                                {% for feedback in feedback_list %}
                                    <div class="col-lg-6 mb-4">
                                        <div class="card feedback-item h-100">
                                            <div class="card-body">
                                                <h5 class="card-title d-flex justify-content-between">
                                                    <span>{{ feedback.name }}</span>
                                                    <span class="badge bg-secondary">{{ feedback.category }}</span>
                                                </h5>
                                                <p class="card-text">{{ feedback.message }}</p>
                                                <div class="feedback-meta d-flex justify-content-between align-items-center">
                                                    <span class="text-muted">
                                                        <i class="far fa-clock me-1"></i> 
                                                        {{ feedback.submitted_at.strftime('%B %d, %Y at %I:%M %p') }}
                                                    </span>
                                                    {% if feedback.sentiment %}
                                                        <span class="
                                                            {% if feedback.sentiment == 'Positive' %}sentiment-positive
                                                            {% elif feedback.sentiment == 'Negative' %}sentiment-negative
                                                            {% else %}sentiment-neutral{% endif %}
                                                        ">
                                                            <i class="
                                                                {% if feedback.sentiment == 'Positive' %}fas fa-smile
                                                                {% elif feedback.sentiment == 'Negative' %}fas fa-frown
                                                                {% else %}fas fa-meh{% endif %} me-1
                                                            "></i>
                                                            {{ feedback.sentiment }}
                                                        </span>
                                                    {% endif %}
                                                </div>
                                                
                                                {% if is_admin %}
                                                <hr>
                                                <div class="text-end">
                                                    <button class="btn btn-sm btn-danger" 
                                                            data-bs-toggle="modal" 
                                                            data-bs-target="#archiveDeleteModal{{ feedback.id }}">
                                                        <i class="fas fa-trash me-1"></i> Delete
                                                    </button>
                                                    
                                                    <!-- Delete Modal -->
                                                    <div class="modal fade" id="archiveDeleteModal{{ feedback.id }}" tabindex="-1">
                                                        <div class="modal-dialog">
                                                            <div class="modal-content">
                                                                <div class="modal-header">
                                                                    <h5 class="modal-title">Confirm Deletion</h5>
                                                                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                                                </div>
                                                                <div class="modal-body">
                                                                    <p>Are you sure you want to delete this feedback from {{ feedback.name }}?</p>
                                                                    <p class="text-danger"><small>This action cannot be undone.</small></p>
                                                                </div>
                                                                <div class="modal-footer">
                                                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                                                    <form action="{{ url_for('delete_feedback_from_archive', feedback_id=feedback.id,
                                                                        category=request.args.get('category', ''), 
                                                                        date_start=request.args.get('date_start', ''),
                                                                        date_end=request.args.get('date_end', ''),
                                                                        search=request.args.get('search', '')) }}" method="post">
                                                                        <button type="submit" class="btn btn-danger">Delete</button>
                                                                    </form>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                                {% endif %}
                                            </div>
                                        </div>
                                    </div>
                                {% endfor %}
                            </div>
                        {% else %}
                            <div class="text-center py-5">
                                <i class="fas fa-search fa-3x mb-3 text-muted"></i>
                                <h4>No feedback found</h4>
                                <p class="text-muted">Try adjusting your filters or search criteria</p>
                                <a href="{{ url_for('archive') }}" class="btn btn-outline-primary">
                                    <i class="fas fa-sync-alt me-2"></i>Clear All Filters
                                </a>
                            </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <footer class="mt-5">
        <div class="container text-center">
            <p class="mb-0">&copy; 2025 Visitor Feedback Archive. All rights reserved.</p>
        </div>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Auto-submit form when category changes
        document.getElementById('category').addEventListener('change', function() {
            document.getElementById('filterForm').submit();
        });
    </script>
</body>
</html>
'''

ADMIN_LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - Feedback Archive</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #4e73df;
            --secondary-color: #6c757d;
            --success-color: #1cc88a;
            --info-color: #36b9cc;
            --warning-color: #f6c23e;
            --danger-color: #e74a3b;
            --light-color: #f8f9fc;
            --dark-color: #5a5c69;
        }
        
        body {
            font-family: 'Nunito', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f8f9fc;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .card {
            border: none;
            box-shadow: 0 .15rem 1.75rem 0 rgba(58,59,69,.15);
        }
        
        .card-header {
            background-color: #f8f9fc;
            border-bottom: 1px solid #e3e6f0;
            font-weight: 700;
            color: var(--primary-color);
        }
        
        .btn-primary {
            background-color: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .btn-primary:hover {
            background-color: #2e59d9;
            border-color: #2653d4;
        }
        
        .form-control:focus {
            border-color: #bac8f3;
            box-shadow: 0 0 0 0.25rem rgba(78, 115, 223, 0.25);
        }
        
        .login-brand {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 1.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-lg-5">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
                
                <div class="card shadow-lg border-0 rounded-lg">
                    <div class="card-header">
                        <h3 class="text-center font-weight-light my-2">Admin Login</h3>
                    </div>
                    <div class="card-body">
                        <div class="text-center mb-4">
                            <div class="login-brand">
                                <i class="fas fa-comments"></i> Feedback Archive
                            </div>
                            <p class="text-muted">Access the admin dashboard to manage feedback</p>
                        </div>
                        
                        <form action="{{ url_for('admin_login') }}" method="post">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <div class="input-group">
                                    <span class="input-group-text">
                                        <i class="fas fa-user"></i>
                                    </span>
                                    <input type="text" class="form-control" id="username" name="username" required>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <label for="password" class="form-label">Password</label>
                                <div class="input-group">
                                    <span class="input-group-text">
                                        <i class="fas fa-lock"></i>
                                    </span>
                                    <input type="password" class="form-control" id="password" name="password" required>
                                </div>
                            </div>
                            
                            <div class="d-grid">
                                <button type="submit" class="btn btn-primary">
                                    <i class="fas fa-sign-in-alt me-2"></i>Login
                                </button>
                            </div>
                        </form>
                    </div>
                    <div class="card-footer text-center py-3">
                        <div class="small">
                            <a href="{{ url_for('index') }}" class="text-decoration-none">
                                <i class="fas fa-arrow-left me-1"></i> Return to Feedback Form
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

ADMIN_DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - Feedback Archive</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #4e73df;
            --secondary-color: #6c757d;
            --success-color: #1cc88a;
            --info-color: #36b9cc;
            --warning-color: #f6c23e;
            --danger-color: #e74a3b;
            --light-color: #f8f9fc;
            --dark-color: #5a5c69;
        }
        
        body {
            font-family: 'Nunito', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f8f9fc;
            color: #5a5c69;
        }
        
        .navbar {
            background-color: white;
            box-shadow: 0 .15rem 1.75rem 0 rgba(58,59,69,.15);
        }
        
        .navbar-brand {
            font-weight: 700;
            color: var(--primary-color);
        }
        
        .card {
            border: none;
            box-shadow: 0 .15rem 1.75rem 0 rgba(58,59,69,.15);
            margin-bottom: 30px;
        }
        
        .card-header {
            background-color: #f8f9fc;
            border-bottom: 1px solid #e3e6f0;
            font-weight: 700;
            color: var(--primary-color);
        }
        
        .btn-primary {
            background-color: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .btn-primary:hover {
            background-color: #2e59d9;
            border-color: #2653d4;
        }
        
        footer {
            background-color: white;
            border-top: 1px solid #e3e6f0;
            padding: 15px 0;
        }
        
        .form-control:focus {
            border-color: #bac8f3;
            box-shadow: 0 0 0 0.25rem rgba(78, 115, 223, 0.25);
        }
        
        .page-header {
            background: linear-gradient(135deg, #4e73df 0%, #224abe 100%);
            color: white;
            padding: 30px 0;
            margin-bottom: 30px;
        }
        
        .stats-card {
            border-left: .25rem solid;
            border-radius: .35rem;
        }
        
        .stats-card-primary {
            border-left-color: var(--primary-color);
        }
        
        .stats-card-success {
            border-left-color: var(--success-color);
        }
        
        .stats-card-info {
            border-left-color: var(--info-color);
        }
        
        .stats-card-warning {
            border-left-color: var(--warning-color);
        }
        
        .stats-icon {
            color: #dddfeb;
            font-size: 2rem;
        }
        
        .stats-text {
            font-size: 0.875rem;
            font-weight: 700;
            color: var(--primary-color);
            text-transform: uppercase;
        }
        
        .stats-number {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--dark-color);
        }
        
        .sentiment-positive {
            color: var(--success-color);
        }
        
        .sentiment-negative {
            color: var(--danger-color);
        }
        
        .sentiment-neutral {
            color: var(--info-color);
        }
        
        .table-responsive {
            max-height: 600px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('admin_dashboard') }}">
                <i class="fas fa-comments me-2"></i>Admin Dashboard
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('index') }}">
                            <i class="fas fa-file-alt me-1"></i> Feedback Form
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('archive') }}">
                            <i class="fas fa-archive me-1"></i> Public Archive
                        </a>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="exportDropdown" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-download me-1"></i> Export
                        </a>
                        <ul class="dropdown-menu" aria-labelledby="exportDropdown">
                            <li>
                                <a class="dropdown-item" href="{{ url_for('export_feedback', format='csv') }}">
                                    <i class="fas fa-file-csv me-2"></i> Export as CSV
                                </a>
                            </li>
                            <li>
                                <a class="dropdown-item" href="{{ url_for('export_feedback', format='pdf') }}">
                                    <i class="fas fa-file-pdf me-2"></i> Export as PDF
                                </a>
                            </li>
                        </ul>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('admin_logout') }}">
                            <i class="fas fa-sign-out-alt me-1"></i> Logout
                        </a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    
    <div class="page-header">
        <div class="container">
            <h1><i class="fas fa-tachometer-alt me-2"></i>Admin Dashboard</h1>
            <p class="lead">Manage and analyze visitor feedback</p>
        </div>
    </div>
    
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <!-- Statistics Row -->
        <div class="row mb-4">
            <!-- Total Feedback -->
            <div class="col-xl-3 col-md-6 mb-4">
                <div class="card stats-card stats-card-primary h-100 py-2">
                    <div class="card-body">
                        <div class="row align-items-center">
                            <div class="col">
                                <div class="stats-text">Total Feedback</div>
                                <div class="stats-number">{{ feedback_list|length }}</div>
                            </div>
                            <div class="col-auto">
                                <i class="fas fa-comments fa-2x stats-icon"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Positive Sentiment -->
            <div class="col-xl-3 col-md-6 mb-4">
                <div class="card stats-card stats-card-success h-100 py-2">
                    <div class="card-body">
                        <div class="row align-items-center">
                            <div class="col">
                                <div class="stats-text">Positive</div>
                                <div class="stats-number">
                                    {{ feedback_list|selectattr('sentiment', 'equalto', 'Positive')|list|length }}
                                </div>
                            </div>
                            <div class="col-auto">
                                <i class="fas fa-smile fa-2x stats-icon"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Neutral Sentiment -->
            <div class="col-xl-3 col-md-6 mb-4">
                <div class="card stats-card stats-card-info h-100 py-2">
                    <div class="card-body">
                        <div class="row align-items-center">
                            <div class="col">
                                <div class="stats-text">Neutral</div>
                                <div class="stats-number">
                                    {{ feedback_list|selectattr('sentiment', 'equalto', 'Neutral')|list|length }}
                                </div>
                            </div>
                            <div class="col-auto">
                                <i class="fas fa-meh fa-2x stats-icon"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Negative Sentiment -->
            <div class="col-xl-3 col-md-6 mb-4">
                <div class="card stats-card stats-card-warning h-100 py-2">
                    <div class="card-body">
                        <div class="row align-items-center">
                            <div class="col">
                                <div class="stats-text">Negative</div>
                                <div class="stats-number">
                                    {{ feedback_list|selectattr('sentiment', 'equalto', 'Negative')|list|length }}
                                </div>
                            </div>
                            <div class="col-auto">
                                <i class="fas fa-frown fa-2x stats-icon"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <i class="fas fa-table me-2"></i>Feedback Management
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-striped" id="feedbackTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Category</th>
                                <th>Message</th>
                                <th>Sentiment</th>
                                <th>Date & Time</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for feedback in feedback_list %}
                                <tr>
                                    <td>{{ feedback.id }}</td>
                                    <td>{{ feedback.name }}</td>
                                    <td>{{ feedback.email or 'N/A' }}</td>
                                    <td>
                                        <span class="badge bg-secondary">{{ feedback.category }}</span>
                                    </td>
                                    <td>
                                        <button class="btn btn-sm btn-outline-primary" 
                                                data-bs-toggle="modal" 
                                                data-bs-target="#messageModal{{ feedback.id }}">
                                            View Message
                                        </button>
                                        
                                        <!-- Message Modal -->
                                        <div class="modal fade" id="messageModal{{ feedback.id }}" tabindex="-1">
                                            <div class="modal-dialog">
                                                <div class="modal-content">
                                                    <div class="modal-header">
                                                        <h5 class="modal-title">Message from {{ feedback.name }}</h5>
                                                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                                    </div>
                                                    <div class="modal-body">
                                                        <p>{{ feedback.message }}</p>
                                                    </div>
                                                    <div class="modal-footer">
                                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </td>
                                    <td>
                                        <span class="
                                            {% if feedback.sentiment == 'Positive' %}sentiment-positive
                                            {% elif feedback.sentiment == 'Negative' %}sentiment-negative
                                            {% else %}sentiment-neutral{% endif %}
                                        ">
                                            <i class="
                                                {% if feedback.sentiment == 'Positive' %}fas fa-smile
                                                {% elif feedback.sentiment == 'Negative' %}fas fa-frown
                                                {% else %}fas fa-meh{% endif %} me-1
                                            "></i>
                                            {{ feedback.sentiment }}
                                        </span>
                                    </td>
                                    <td>{{ feedback.submitted_at.strftime('%Y-%m-%d %H:%M') }}</td>
                                    <td>
                                        <button class="btn btn-sm btn-danger" 
                                                data-bs-toggle="modal" 
                                                data-bs-target="#deleteModal{{ feedback.id }}">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                        
                                        <!-- Delete Modal -->
                                        <div class="modal fade" id="deleteModal{{ feedback.id }}" tabindex="-1">
                                            <div class="modal-dialog">
                                                <div class="modal-content">
                                                    <div class="modal-header">
                                                        <h5 class="modal-title">Confirm Deletion</h5>
                                                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                                    </div>
                                                    <div class="modal-body">
                                                        <p>Are you sure you want to delete this feedback from {{ feedback.name }}?</p>
                                                        <p class="text-danger"><small>This action cannot be undone.</small></p>
                                                    </div>
                                                    <div class="modal-footer">
                                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                                        <form action="{{ url_for('delete_feedback', feedback_id=feedback.id) }}" method="post">
                                                            <button type="submit" class="btn btn-danger">Delete</button>
                                                        </form>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <footer class="mt-5">
        <div class="container text-center">
            <p class="mb-0">&copy; 2025 Visitor Feedback Archive. All rights reserved.</p>
        </div>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

PDF_EXPORT_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Feedback Export</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
        }
        h1 {
            color: #4e73df;
            text-align: center;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .export-date {
            color: #6c757d;
            font-style: italic;
            text-align: center;
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th {
            background-color: #4e73df;
            color: white;
            text-align: left;
            padding: 8px;
        }
        td {
            border: 1px solid #ddd;
            padding: 8px;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        .footer {
            margin-top: 30px;
            text-align: center;
            font-size: 12px;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Visitor Feedback Export</h1>
    </div>
    
    <div class="export-date">
        Generated on {{ datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC') }}
    </div>
    
    {{ table|safe }}
    
    <div class="footer">
        <p>© 2025 Visitor Feedback Archive System</p>
    </div>
</body>
</html>
'''

# Run the application
if __name__ == '__main__':
    app.run(debug=True)