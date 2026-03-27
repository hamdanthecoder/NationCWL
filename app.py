from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nationcwl-super-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nationcwl.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

db = SQLAlchemy(app)

# ── Models ──────────────────────────────────────────────────────────────────

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    worksheets = db.relationship('Worksheet', backref='uploaded_by', lazy=True)

class Worksheet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200), nullable=False)
    month = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    file_size = db.Column(db.Integer)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── Helpers ─────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_superadmin'):
            flash('Only the Super Admin can perform this action.', 'error')
            return redirect(url_for('admins'))
        return f(*args, **kwargs)
    return decorated

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024*1024):.1f} MB"

app.jinja_env.globals['format_size'] = format_size

MONTHS = ['January','February','March','April','May','June',
          'July','August','September','October','November','December']

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        admin = Admin.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password, password):
            session['admin_id'] = admin.id
            session['admin_name'] = admin.name
            session['admin_email'] = admin.email
            session['is_superadmin'] = (admin.role == 'superadmin')
            flash(f'Welcome back, {admin.name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    worksheets = Worksheet.query.order_by(Worksheet.created_at.desc()).all()
    admins = Admin.query.all()
    total_size = sum(w.file_size or 0 for w in worksheets)
    return render_template('dashboard.html',
                           worksheets=worksheets,
                           admins=admins,
                           total_size=total_size,
                           months=MONTHS,
                           current_year=datetime.now().year,
                           is_superadmin=session.get('is_superadmin', False))

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('dashboard'))
    file = request.files['file']
    month = request.form.get('month')
    year = request.form.get('year')
    description = request.form.get('description', '')

    if not file or file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('dashboard'))
    if not allowed_file(file.filename):
        flash('Only Excel (.xlsx, .xls) and CSV files are allowed.', 'error')
        return redirect(url_for('dashboard'))

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    saved_name = timestamp + filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
    file.save(file_path)
    size = os.path.getsize(file_path)

    ws = Worksheet(
        filename=saved_name,
        original_name=filename,
        month=month,
        year=int(year),
        description=description,
        file_size=size,
        admin_id=session['admin_id']
    )
    db.session.add(ws)
    db.session.commit()
    flash(f'Worksheet "{filename}" uploaded successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/download/<int:ws_id>')
@login_required
def download(ws_id):
    ws = Worksheet.query.get_or_404(ws_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], ws.filename,
                               as_attachment=True, download_name=ws.original_name)

@app.route('/delete/<int:ws_id>', methods=['POST'])
@login_required
def delete_worksheet(ws_id):
    ws = Worksheet.query.get_or_404(ws_id)
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], ws.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(ws)
        db.session.commit()
        flash(f'Worksheet "{ws.original_name}" deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admins')
@login_required
def admins():
    all_admins = Admin.query.all()
    return render_template('admins.html', admins=all_admins)

@app.route('/admins/add', methods=['POST'])
@login_required
@superadmin_required
def add_admin():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    if not name or not email or not password:
        flash('All fields are required.', 'error')
        return redirect(url_for('admins'))
    if Admin.query.filter_by(email=email).first():
        flash('Email already exists.', 'error')
        return redirect(url_for('admins'))
    admin = Admin(name=name, email=email,
                  password=generate_password_hash(password))
    db.session.add(admin)
    db.session.commit()
    flash(f'Admin "{name}" added successfully!', 'success')
    return redirect(url_for('admins'))

@app.route('/admins/change-password', methods=['POST'])
@login_required
def change_own_password():
    current = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    admin = Admin.query.get(session['admin_id'])
    if not check_password_hash(admin.password, current):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('admins'))
    if len(new_pw) < 6:
        flash('New password must be at least 6 characters.', 'error')
        return redirect(url_for('admins'))
    if new_pw != confirm:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('admins'))
    admin.password = generate_password_hash(new_pw)
    db.session.commit()
    flash('Your password has been updated successfully!', 'success')
    return redirect(url_for('admins'))

@app.route('/admins/reset-password/<int:admin_id>', methods=['POST'])
@login_required
@superadmin_required
def reset_admin_password(admin_id):
    new_pw = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    if len(new_pw) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('admins'))
    if new_pw != confirm:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('admins'))
    admin = Admin.query.get_or_404(admin_id)
    admin.password = generate_password_hash(new_pw)
    db.session.commit()
    flash(f'Password for "{admin.name}" has been reset successfully!', 'success')
    return redirect(url_for('admins'))

@app.route('/admins/delete/<int:admin_id>', methods=['POST'])
@login_required
@superadmin_required
def delete_admin(admin_id):
    if admin_id == session['admin_id']:
        flash("You can't delete your own account.", 'error')
        return redirect(url_for('admins'))
    admin = Admin.query.get_or_404(admin_id)
    if admin.role == 'superadmin':
        flash("The Super Admin account cannot be deleted.", 'error')
        return redirect(url_for('admins'))
    db.session.delete(admin)
    db.session.commit()
    flash(f'Admin "{admin.name}" removed.', 'success')
    return redirect(url_for('admins'))

# ── Init ──────────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        if Admin.query.count() == 0:
            default = Admin(
                name='Super Admin',
                email='admin@nationcwl.com',
                password=generate_password_hash('admin123'),
                role='superadmin'
            )
            db.session.add(default)
            db.session.commit()
            print("✅ Default admin created: admin@nationcwl.com / admin123")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
