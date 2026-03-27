# NationCWL Signup Portal

A Flask-based admin portal for uploading and managing monthly Google Worksheets.

## Features
- 🔐 Secure admin login
- 📂 Upload Excel (.xlsx, .xls) and CSV worksheets
- 📅 Tag worksheets by month and year
- 👥 Up to 3 admin accounts
- 📊 Dashboard with stats
- 🗑️ Delete & download files

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python app.py
```

Then open: http://127.0.0.1:5000

## Default Login
- Email: `admin@nationcwl.com`
- Password: `admin123`

> ⚠️ Change the default password after first login!

## Project Structure
```
nationcwlsignup/
├── app.py                  # Main Flask app
├── requirements.txt
├── templates/
│   ├── base.html           # Base layout
│   ├── login.html          # Login page
│   ├── dashboard.html      # Main dashboard
│   └── admins.html         # Admin management
├── static/
│   └── uploads/            # Uploaded files stored here
└── instance/
    └── nationcwl.db        # SQLite database (auto-created)
```
