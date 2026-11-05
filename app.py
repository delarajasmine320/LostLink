import os
from functools import wraps
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
ALLOWED = {"png", "jpg", "jpeg", "webp"}
login_manager = LoginManager(app)
login_manager.login_view = "login"

def db():
    return mysql.connector.connect(host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"], password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DATABASE"])

class User(UserMixin):
    def __init__(self, row):
        self.id, self.full_name, self.email, self.role = row["id"], row["full_name"], row["email"], row["role"]

@login_manager.user_loader
def load_user(uid):
    conn=db(); cur=conn.cursor(dictionary=True)
    cur.execute("SELECT id,full_name,email,role FROM users WHERE id=%s",(uid,))
    row=cur.fetchone(); cur.close(); conn.close()
    return User(row) if row else None

def staff_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*a, **kw):
        if current_user.role not in ("admin","staff"): abort(403)
        return fn(*a, **kw)
    return wrapped

def image_ok(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED

@app.route("/")
def index():
    conn=db(); cur=conn.cursor(dictionary=True)
    cur.execute("""SELECT i.*,u.full_name reporter FROM items i JOIN users u ON u.id=i.user_id
                   WHERE i.status='published' ORDER BY i.created_at DESC LIMIT 6""")
    items=cur.fetchall(); cur.close(); conn.close()
    return render_template("index.html",items=items)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("full_name","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not name or not email or len(password)<8:
            flash("Complete all fields. Password must have at least 8 characters.","error")
        else:
            conn=db(); cur=conn.cursor()
            try:
                cur.execute("INSERT INTO users(full_name,email,password_hash) VALUES(%s,%s,%s)",
                    (name,email,generate_password_hash(password)))
                conn.commit(); flash("Account created. Please log in.","success")
                return redirect(url_for("login"))
            except mysql.connector.Error:
                conn.rollback(); flash("That email may already be registered.","error")
            finally:
                cur.close(); conn.close()
    return render_template("register.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        conn=db(); cur=conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s",(request.form.get("email","").strip().lower(),))
        row=cur.fetchone(); cur.close(); conn.close()
        if row and check_password_hash(row["password_hash"],request.form.get("password","")):
            login_user(User(row)); return redirect(url_for("dashboard"))
        flash("Incorrect email or password.","error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user(); return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn=db(); cur=conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) total FROM items WHERE user_id=%s",(current_user.id,))
    reports=cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) total FROM claims WHERE claimant_id=%s AND status='pending'",(current_user.id,))
    claims=cur.fetchone()["total"]
    cur.execute("SELECT * FROM items WHERE user_id=%s ORDER BY created_at DESC LIMIT 8",(current_user.id,))
    items=cur.fetchall(); cur.close(); conn.close()
    return render_template("dashboard.html",reports=reports,claims=claims,items=items)

@app.route("/report/<kind>",methods=["GET","POST"])
@login_required
def report(kind):
    if kind not in ("lost","found"): abort(404)
    if request.method=="POST":
        fields=[request.form.get(x,"").strip() for x in ("item_name","category","description","location","incident_date")]
        if not all(fields):
            flash("Please complete all required fields.","error")
        else:
            photo=request.files.get("image"); filename=None
            if photo and photo.filename:
                if not image_ok(photo.filename):
                    flash("Use a PNG, JPG, JPEG, or WEBP image.","error")
                    return render_template("report.html",kind=kind)
                filename=secure_filename(photo.filename)
                filename=f"{current_user.id}_{filename}"
                photo.save(os.path.join(app.config["UPLOAD_FOLDER"],filename))
            conn=db(); cur=conn.cursor()
            cur.execute("""INSERT INTO items(user_id,report_type,item_name,category,description,location,incident_date,image_filename)
                           VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (current_user.id,kind,*fields,filename))
            conn.commit(); cur.close(); conn.close()
            flash("Your report has been submitted.","success")
            return redirect(url_for("dashboard"))
    return render_template("report.html",kind=kind)

@app.route("/items")
def items():
    q=request.args.get("q","").strip(); kind=request.args.get("type","")
    conn=db(); cur=conn.cursor(dictionary=True)
    sql="""SELECT i.*,u.full_name reporter FROM items i JOIN users u ON u.id=i.user_id
           WHERE i.status='published'"""
    args=[]
    if q:
        sql+=" AND (i.item_name LIKE %s OR i.description LIKE %s OR i.location LIKE %s)"
        args += [f"%{q}%"]*3
    if kind in ("lost","found"):
        sql+=" AND i.report_type=%s"; args.append(kind)
    sql+=" ORDER BY i.created_at DESC"
    cur.execute(sql,tuple(args)); rows=cur.fetchall(); cur.close(); conn.close()
    return render_template("items.html",items=rows,q=q,kind=kind)

@app.route("/items/<int:item_id>")
def item_detail(item_id):
    conn=db(); cur=conn.cursor(dictionary=True)
    cur.execute("""SELECT i.*,u.full_name reporter FROM items i JOIN users u ON u.id=i.user_id WHERE i.id=%s""",(item_id,))
    item=cur.fetchone(); cur.close(); conn.close()
    if not item: abort(404)
    return render_template("item_detail.html",item=item)

@app.route("/items/<int:item_id>/claim",methods=["POST"])
@login_required
def claim(item_id):
    details=request.form.get("ownership_details","").strip()
    conn=db(); cur=conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM items WHERE id=%s AND report_type='found' AND status='published'",(item_id,))
    item=cur.fetchone()
    if not item or item["user_id"]==current_user.id or not details:
        cur.close(); conn.close(); flash("Unable to submit this claim. Check the item and details.","error")
        return redirect(url_for("item_detail",item_id=item_id))
    cur.execute("INSERT INTO claims(item_id,claimant_id,ownership_details) VALUES(%s,%s,%s)",(item_id,current_user.id,details))
    cur.execute("INSERT INTO notifications(user_id,message) VALUES(%s,%s)",(item["user_id"],f"A claim was submitted for {item['item_name']}."))
    conn.commit(); cur.close(); conn.close()
    flash("Claim submitted for staff verification.","success")
    return redirect(url_for("dashboard"))

@app.route("/staff/claims")
@staff_required
def claims():
    conn=db(); cur=conn.cursor(dictionary=True)
    cur.execute("""SELECT c.*,i.item_name,u.full_name claimant FROM claims c
                   JOIN items i ON i.id=c.item_id JOIN users u ON u.id=c.claimant_id
                   ORDER BY c.created_at DESC""")
    rows=cur.fetchall(); cur.close(); conn.close()
    return render_template("claims.html",claims=rows)

@app.route("/staff/claims/<int:cid>/<decision>",methods=["POST"])
@staff_required
def decide_claim(cid,decision):
    if decision not in ("approved","rejected"): abort(400)
    conn=db(); cur=conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM claims WHERE id=%s",(cid,)); c=cur.fetchone()
    if not c or c["status"]!="pending":
        cur.close(); conn.close(); flash("Claim not found or already processed.","error")
        return redirect(url_for("claims"))
    cur.execute("UPDATE claims SET status=%s WHERE id=%s",(decision,cid))
    if decision=="approved":
        cur.execute("UPDATE items SET status='claimed' WHERE id=%s",(c["item_id"],))
    cur.execute("INSERT INTO notifications(user_id,message) VALUES(%s,%s)",(c["claimant_id"],f"Your claim was {decision}."))
    conn.commit(); cur.close(); conn.close()
    flash(f"Claim {decision}.","success"); return redirect(url_for("claims"))

@app.route("/notifications")
@login_required
def notifications():
    conn=db(); cur=conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC",(current_user.id,))
    rows=cur.fetchall()
    cur.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s",(current_user.id,))
    conn.commit(); cur.close(); conn.close()
    return render_template("notifications.html",notifications=rows)

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html",code=403,message="You do not have permission to view this page."),403
@app.errorhandler(404)
def missing(e):
    return render_template("error.html",code=404,message="The requested page or item was not found."),404

if __name__=="__main__":
    app.run(debug=True)
