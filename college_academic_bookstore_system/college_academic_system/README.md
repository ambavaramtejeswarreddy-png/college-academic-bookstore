# College Academic Bookstore and Semester Study Material System

A beginner-friendly Flask + SQLite web application for a college bookstore and semester-wise study resource portal.

## Features
- Student registration and login (passwords are hashed)
- Browse/search academic books by keyword and semester
- Shopping cart, stock checking, demo checkout, and order history
- Browse and download semester/department/subject study files
- Admin dashboard to add/delete books and upload/delete materials
- SQLite database is created automatically with sample books and a demo admin

## Requirements
- Python 3.10 or newer
- Internet connection only for installing Flask

## Run on Windows
1. Extract this ZIP file.
2. Open the extracted `college_academic_system` folder in VS Code.
3. Open Terminal in VS Code.
4. Create a virtual environment:
   ```powershell
   py -m venv venv
   ```
5. Activate it:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.
6. Install Flask:
   ```powershell
   python -m pip install -r requirements.txt
   ```
7. Start the website:
   ```powershell
   python app.py
   ```
8. Open `http://127.0.0.1:5000` in your browser.

## Demo administrator login
- Email: `admin@college.local`
- Password: `Admin@123`

Change this password and the `SECRET_KEY` before deploying anywhere beyond a local classroom demo. The database file `college.db` is created in the project folder the first time the app runs.

## Suggested demonstration
1. Register a student account.
2. Log in and browse books.
3. Add a book to the cart and place a demo order.
4. Open My Orders to show order history.
5. Log out and sign in as the administrator.
6. Add a book and upload a PDF/DOC/PPT study resource.
7. Log in as a student and download the resource.

## Notes / scope
- Checkout is a classroom demonstration using "Pay at College"; it does not process real payments.
- This starter project does not send email, verify student enrollment, or provide cloud hosting.
- For public deployment, add CSRF protection, rate limiting, stronger upload validation and malware scanning, secure production secrets, HTTPS, backups, and a production WSGI server. Do not use Flask debug mode in production.
