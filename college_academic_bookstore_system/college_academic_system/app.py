import os, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "college.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx"}

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'student');
        CREATE TABLE IF NOT EXISTS books(
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
          author TEXT NOT NULL, subject TEXT NOT NULL, semester TEXT NOT NULL,
          department TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL DEFAULT 0,
          description TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS materials(
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
          subject TEXT NOT NULL, semester TEXT NOT NULL, department TEXT NOT NULL,
          material_type TEXT NOT NULL, filename TEXT NOT NULL,
          uploaded_by INTEGER REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS orders(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
          total REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Placed',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS order_items(
          id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL REFERENCES orders(id),
          book_id INTEGER NOT NULL REFERENCES books(id), quantity INTEGER NOT NULL,
          price REAL NOT NULL);
        """)
        if not con.execute("SELECT id FROM users WHERE email=?", ("admin@college.local",)).fetchone():
            con.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                        ("Administrator","admin@college.local",generate_password_hash("Admin@123"),"admin"))
        if not con.execute("SELECT id FROM books LIMIT 1").fetchone():
            samples=[
              ("Python Programming","Reema Thareja","Python","2","CSE",450,20,"Beginner-friendly programming textbook."),
              ("Database System Concepts","Abraham Silberschatz","DBMS","3","CSE",650,12,"Database fundamentals and SQL."),
              ("Computer Networks","Andrew Tanenbaum","Networks","4","CSE",550,8,"Networking concepts and protocols.")
            ]
            con.executemany("INSERT INTO books(title,author,subject,semester,department,price,stock,description) VALUES(?,?,?,?,?,?,?,?)",samples)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in first.")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    with db() as con:
        books=con.execute("SELECT * FROM books ORDER BY id DESC LIMIT 6").fetchall()
        materials=con.execute("SELECT * FROM materials ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("index.html", books=books, materials=materials)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form["name"].strip(); email=request.form["email"].strip().lower()
        password=request.form["password"]
        if len(password)<8:
            flash("Password must contain at least 8 characters."); return redirect(url_for("register"))
        try:
            with db() as con:
                con.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                            (name,email,generate_password_hash(password)))
            flash("Account created. Please log in."); return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email address is already registered.")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"].strip().lower(); password=request.form["password"]
        with db() as con:
            user=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if user and check_password_hash(user["password"],password):
            session.clear(); session.update(user_id=user["id"],name=user["name"],role=user["role"])
            return redirect(url_for("admin") if user["role"]=="admin" else url_for("index"))
        flash("Invalid email or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); flash("You have been logged out."); return redirect(url_for("index"))

@app.route("/books")
def books():
    q=request.args.get("q","").strip(); semester=request.args.get("semester","")
    with db() as con:
        rows=con.execute("""SELECT * FROM books WHERE
          (title LIKE ? OR author LIKE ? OR subject LIKE ?) AND (?='' OR semester=?)
          ORDER BY title""",(f"%{q}%",f"%{q}%",f"%{q}%",semester,semester)).fetchall()
    return render_template("books.html",books=rows,q=q,semester=semester)

@app.route("/cart/add/<int:book_id>", methods=["POST"])
@login_required
def add_cart(book_id):
    with db() as con:
        book=con.execute("SELECT * FROM books WHERE id=?",(book_id,)).fetchone()
    if not book or book["stock"]<1:
        flash("This book is currently out of stock.")
    else:
        cart=session.get("cart",{})
        key=str(book_id); cart[key]=min(int(cart.get(key,0))+1,book["stock"])
        session["cart"]=cart; flash("Book added to cart.")
    return redirect(request.referrer or url_for("books"))

@app.route("/cart")
@login_required
def cart():
    cart_data=[]; total=0
    with db() as con:
        for book_id,qty in session.get("cart",{}).items():
            book=con.execute("SELECT * FROM books WHERE id=?",(int(book_id),)).fetchone()
            if book:
                subtotal=book["price"]*qty; total+=subtotal
                cart_data.append({"book":book,"qty":qty,"subtotal":subtotal})
    return render_template("cart.html",items=cart_data,total=total)

@app.route("/cart/remove/<int:book_id>", methods=["POST"])
@login_required
def remove_cart(book_id):
    cart=session.get("cart",{}); cart.pop(str(book_id),None); session["cart"]=cart
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    cart=session.get("cart",{})
    if not cart: flash("Your cart is empty."); return redirect(url_for("cart"))
    with db() as con:
        items=[]; total=0
        for book_id,qty in cart.items():
            book=con.execute("SELECT * FROM books WHERE id=?",(int(book_id),)).fetchone()
            if not book or qty>book["stock"]:
                flash("Stock changed. Please review your cart."); return redirect(url_for("cart"))
            items.append((book,int(qty))); total+=book["price"]*int(qty)
        cur=con.execute("INSERT INTO orders(user_id,total) VALUES(?,?)",(session["user_id"],total))
        order_id=cur.lastrowid
        for book,qty in items:
            con.execute("INSERT INTO order_items(order_id,book_id,quantity,price) VALUES(?,?,?,?)",
                        (order_id,book["id"],qty,book["price"]))
            con.execute("UPDATE books SET stock=stock-? WHERE id=?",(qty,book["id"]))
    session["cart"]={}; flash(f"Order #{order_id} placed. Payment is marked as Pay at College (demo).")
    return redirect(url_for("my_orders"))

@app.route("/my-orders")
@login_required
def my_orders():
    with db() as con:
        orders=con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall()
        details={}
        for order in orders:
            details[order["id"]]=con.execute("""SELECT oi.*,b.title FROM order_items oi
              JOIN books b ON b.id=oi.book_id WHERE oi.order_id=?""",(order["id"],)).fetchall()
    return render_template("orders.html",orders=orders,details=details)

@app.route("/materials")
def materials():
    q=request.args.get("q","").strip(); sem=request.args.get("semester","")
    with db() as con:
        rows=con.execute("""SELECT * FROM materials WHERE
          (title LIKE ? OR subject LIKE ? OR material_type LIKE ?) AND (?='' OR semester=?)
          ORDER BY id DESC""",(f"%{q}%",f"%{q}%",f"%{q}%",sem,sem)).fetchall()
    return render_template("materials.html",materials=rows,q=q,semester=sem)

@app.route("/uploads/<path:filename>")
def download(filename):
    # Only files recorded in the materials table can be downloaded.
    with db() as con:
        row=con.execute("SELECT id FROM materials WHERE filename=?",(filename,)).fetchone()
    if not row: abort(404)
    return send_from_directory(UPLOAD_DIR,filename,as_attachment=True)

@app.route("/admin")
@login_required
@admin_required
def admin():
    with db() as con:
        counts={
          "books":con.execute("SELECT COUNT(*) FROM books").fetchone()[0],
          "materials":con.execute("SELECT COUNT(*) FROM materials").fetchone()[0],
          "orders":con.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
          "students":con.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]}
        orders=con.execute("""SELECT o.*,u.name FROM orders o JOIN users u ON u.id=o.user_id
                              ORDER BY o.id DESC LIMIT 10""").fetchall()
    return render_template("admin.html",counts=counts,orders=orders)

@app.route("/admin/books",methods=["GET","POST"])
@login_required
@admin_required
def manage_books():
    if request.method=="POST":
        f=request.form
        try:
            with db() as con:
                con.execute("""INSERT INTO books(title,author,subject,semester,department,price,stock,description)
                  VALUES(?,?,?,?,?,?,?,?)""",(f["title"],f["author"],f["subject"],f["semester"],f["department"],
                  float(f["price"]),int(f["stock"]),f.get("description","")))
            flash("Book added.")
        except ValueError: flash("Enter a valid price and stock quantity.")
        return redirect(url_for("manage_books"))
    with db() as con: rows=con.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    return render_template("manage_books.html",books=rows)

@app.route("/admin/books/delete/<int:book_id>",methods=["POST"])
@login_required
@admin_required
def delete_book(book_id):
    with db() as con:
        if con.execute("SELECT 1 FROM order_items WHERE book_id=?",(book_id,)).fetchone():
            flash("Cannot delete a book that appears in an order.")
        else: con.execute("DELETE FROM books WHERE id=?",(book_id,)); flash("Book deleted.")
    return redirect(url_for("manage_books"))

@app.route("/admin/materials",methods=["GET","POST"])
@login_required
@admin_required
def manage_materials():
    if request.method=="POST":
        f=request.form; upload=request.files.get("file")
        if not upload or not upload.filename:
            flash("Choose a file to upload."); return redirect(url_for("manage_materials"))
        filename=secure_filename(upload.filename)
        ext=filename.rsplit(".",1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            flash("Allowed file types: PDF, DOC, DOCX, PPT, PPTX."); return redirect(url_for("manage_materials"))
        # Prefix avoids collisions between files with the same name.
        import uuid
        stored=f"{uuid.uuid4().hex}_{filename}"
        upload.save(os.path.join(UPLOAD_DIR,stored))
        with db() as con:
            con.execute("""INSERT INTO materials(title,subject,semester,department,material_type,filename,uploaded_by)
              VALUES(?,?,?,?,?,?,?)""",(f["title"],f["subject"],f["semester"],f["department"],
              f["material_type"],stored,session["user_id"]))
        flash("Study material uploaded."); return redirect(url_for("manage_materials"))
    with db() as con: rows=con.execute("SELECT * FROM materials ORDER BY id DESC").fetchall()
    return render_template("manage_materials.html",materials=rows)

@app.route("/admin/materials/delete/<int:material_id>",methods=["POST"])
@login_required
@admin_required
def delete_material(material_id):
    with db() as con:
        row=con.execute("SELECT filename FROM materials WHERE id=?",(material_id,)).fetchone()
        if row:
            path=os.path.join(UPLOAD_DIR,row["filename"])
            if os.path.isfile(path): os.remove(path)
            con.execute("DELETE FROM materials WHERE id=?",(material_id,))
    flash("Material deleted."); return redirect(url_for("manage_materials"))

@app.errorhandler(403)
def forbidden(_): return render_template("message.html",title="Access denied",message="Only administrators can open this page."),403
@app.errorhandler(404)
def missing(_): return render_template("message.html",title="Not found",message="The requested page or file does not exist."),404

init_db()

if __name__ == "__main__":
    app.run(debug=True)