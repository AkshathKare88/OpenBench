from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os
from datetime import datetime, timedelta
from functools import wraps

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "openbench.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "openbench-local-demo-key-change-before-deployment")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_event(conn, actor, action, entity_type, entity_id, details=""):
    conn.execute(
        "INSERT INTO audit_events(actor, action, entity_type, entity_id, details, created_at) VALUES(?,?,?,?,?,?)",
        (actor, action, entity_type, entity_id, details, now())
    )

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student','owner','admin')),
        trained_electronics INTEGER NOT NULL DEFAULT 0,
        trained_3d_printer INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        location TEXT NOT NULL,
        description TEXT NOT NULL,
        requirements TEXT NOT NULL DEFAULT '',
        required_training TEXT NOT NULL DEFAULT 'none',
        owner_id INTEGER NOT NULL,
        available INTEGER NOT NULL DEFAULT 1,
        condition_status TEXT NOT NULL DEFAULT 'Good',
        FOREIGN KEY(owner_id) REFERENCES profiles(id)
    );
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        start_at TEXT NOT NULL,
        end_at TEXT NOT NULL,
        purpose TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        decision_reason TEXT NOT NULL DEFAULT '',
        checked_in_at TEXT,
        checked_out_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(resource_id) REFERENCES resources(id),
        FOREIGN KEY(user_id) REFERENCES profiles(id)
    );
    CREATE TABLE IF NOT EXISTS condition_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        report_type TEXT NOT NULL,
        condition_label TEXT NOT NULL,
        notes TEXT NOT NULL DEFAULT '',
        created_by INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(booking_id) REFERENCES bookings(id),
        FOREIGN KEY(created_by) REFERENCES profiles(id)
    );
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        reporter_id INTEGER NOT NULL,
        incident_type TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        resolution TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(booking_id) REFERENCES bookings(id),
        FOREIGN KEY(reporter_id) REFERENCES profiles(id)
    );
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        details TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    """)
    count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    if count == 0:
        conn.execute("INSERT INTO profiles(name, role, trained_electronics, trained_3d_printer) VALUES('Aarav Demo Student','student',1,1)")
        conn.execute("INSERT INTO profiles(name, role, trained_electronics, trained_3d_printer) VALUES('Mira Demo Student','student',0,0)")
        conn.execute("INSERT INTO profiles(name, role) VALUES('Lab Manager Demo','owner')")
        conn.execute("INSERT INTO profiles(name, role) VALUES('Platform Admin Demo','admin')")
        owner_id = conn.execute("SELECT id FROM profiles WHERE role='owner'").fetchone()[0]
        resources = [
            ("Digital Oscilloscope", "Electronics", "Engineering Lab A", "Measure and inspect electronic signals for project work.", "Electronics-lab training required; supervised use.", "electronics", owner_id, 1, "Good"),
            ("FDM 3D Printer", "Fabrication", "Makerspace", "Print prototypes using approved filament and supervised time slots.", "3D-printer training required; follow lab safety rules.", "3d_printer", owner_id, 1, "Good"),
            ("Project Room 2B", "Study Space", "Innovation Block, Floor 2", "Small project room for team collaboration and prototyping.", "Leave the room tidy and return keys to the desk.", "none", owner_id, 1, "Good"),
        ]
        conn.executemany("""INSERT INTO resources(name,category,location,description,requirements,required_training,owner_id,available,condition_status)
                            VALUES(?,?,?,?,?,?,?,?,?)""", resources)
        log_event(conn, "System", "SEEDED_DEMO_DATA", "system", 1, "Created fictional demo users and resources")
    conn.commit()
    conn.close()

def current_user():
    if "user_id" not in session:
        return None
    conn = db()
    user = conn.execute("SELECT * FROM profiles WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return user

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Choose a demo account to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login"))
            if user["role"] not in roles:
                flash("That action requires a different role.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapped
    return decorator

def is_eligible(user, resource):
    req = resource["required_training"]
    if req == "electronics":
        return bool(user["trained_electronics"])
    if req == "3d_printer":
        return bool(user["trained_3d_printer"])
    return True

@app.route("/")
def index():
    conn = db()
    resources = conn.execute("SELECT resources.*, profiles.name AS owner_name FROM resources JOIN profiles ON profiles.id=resources.owner_id ORDER BY resources.id").fetchall()
    conn.close()
    return render_template("index.html", resources=resources, user=current_user())

@app.route("/login", methods=["GET", "POST"])
def login():
    conn = db()
    users = conn.execute("SELECT * FROM profiles ORDER BY id").fetchall()
    if request.method == "POST":
        try:
            uid = int(request.form.get("user_id", ""))
        except ValueError:
            uid = 0
        user = conn.execute("SELECT * FROM profiles WHERE id=?", (uid,)).fetchone()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            flash(f"Signed in as {user['name']} (demo account).", "success")
            return redirect(url_for("dashboard"))
        flash("Please choose a valid demo account.", "error")
        return redirect(url_for("login"))
    conn.close()
    return render_template("login.html", users=users, user=current_user())

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    conn = db()
    if user["role"] == "owner":
        bookings = conn.execute("""SELECT b.*, r.name AS resource_name, p.name AS user_name
            FROM bookings b JOIN resources r ON r.id=b.resource_id JOIN profiles p ON p.id=b.user_id
            WHERE r.owner_id=? ORDER BY b.created_at DESC""", (user["id"],)).fetchall()
    elif user["role"] == "admin":
        bookings = conn.execute("""SELECT b.*, r.name AS resource_name, p.name AS user_name
            FROM bookings b JOIN resources r ON r.id=b.resource_id JOIN profiles p ON p.id=b.user_id
            ORDER BY b.created_at DESC""").fetchall()
    else:
        bookings = conn.execute("""SELECT b.*, r.name AS resource_name, p.name AS user_name
            FROM bookings b JOIN resources r ON r.id=b.resource_id JOIN profiles p ON p.id=b.user_id
            WHERE b.user_id=? ORDER BY b.created_at DESC""", (user["id"],)).fetchall()
    resources = conn.execute("SELECT * FROM resources ORDER BY name").fetchall()
    conn.close()
    return render_template("dashboard.html", user=user, bookings=bookings, resources=resources)

@app.route("/resource/<int:resource_id>")
def resource_detail(resource_id):
    conn = db()
    resource = conn.execute("""SELECT resources.*, profiles.name AS owner_name
        FROM resources JOIN profiles ON profiles.id=resources.owner_id WHERE resources.id=?""", (resource_id,)).fetchone()
    conn.close()
    if not resource:
        flash("Resource not found.", "error")
        return redirect(url_for("index"))
    user = current_user()
    eligible = is_eligible(user, resource) if user else None
    return render_template("resource.html", resource=resource, user=user, eligible=eligible)

@app.route("/resource/new", methods=["GET", "POST"])
@login_required
@role_required("owner", "admin")
def new_resource():
    user = current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        requirements = request.form.get("requirements", "").strip()
        training = request.form.get("required_training", "none")
        if training not in ("none", "electronics", "3d_printer"):
            flash("Choose a valid training requirement.", "error")
            return redirect(url_for("new_resource"))
        if not all([name, category, location, description]):
            flash("Please complete all required fields.", "error")
            return redirect(url_for("new_resource"))
        conn = db()
        cur = conn.execute("""INSERT INTO resources(name,category,location,description,requirements,required_training,owner_id)
            VALUES(?,?,?,?,?,?,?)""", (name, category, location, description, requirements, training, user["id"]))
        rid = cur.lastrowid
        log_event(conn, user["name"], "RESOURCE_LISTED", "resource", rid, name)
        conn.commit()
        conn.close()
        flash("Resource listed successfully.", "success")
        return redirect(url_for("resource_detail", resource_id=rid))
    return render_template("new_resource.html", user=user)

@app.route("/book/<int:resource_id>", methods=["POST"])
@login_required
@role_required("student")
def book_resource(resource_id):
    user = current_user()
    conn = db()
    # Serialize competing booking submissions before checking the slot.
    conn.execute("BEGIN IMMEDIATE")
    resource = conn.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
    if not resource:
        conn.close()
        flash("Resource not found.", "error")
        return redirect(url_for("index"))
    if not is_eligible(user, resource):
        conn.close()
        flash("You do not meet this resource's training requirement.", "error")
        return redirect(url_for("resource_detail", resource_id=resource_id))
    if not resource["available"]:
        conn.close()
        flash("This resource is temporarily unavailable.", "error")
        return redirect(url_for("resource_detail", resource_id=resource_id))
    start_at = request.form.get("start_at", "").strip()
    end_at = request.form.get("end_at", "").strip()
    purpose = request.form.get("purpose", "").strip()
    if not start_at or not end_at or not purpose:
        conn.close()
        flash("Please provide a time slot and purpose.", "error")
        return redirect(url_for("resource_detail", resource_id=resource_id))
    try:
        start = datetime.fromisoformat(start_at)
        end = datetime.fromisoformat(end_at)
        if start.tzinfo is not None or end.tzinfo is not None:
            raise ValueError()
        if end <= start or start < datetime.now() - timedelta(minutes=1):
            raise ValueError()
    except (ValueError, TypeError):
        conn.close()
        flash("Please choose a valid future time range.", "error")
        return redirect(url_for("resource_detail", resource_id=resource_id))
    conflict = conn.execute("""SELECT id FROM bookings WHERE resource_id=? AND status IN ('pending','approved','checked_in')
        AND start_at < ? AND end_at > ?""", (resource_id, end_at.replace("T", " "), start_at.replace("T", " "))).fetchone()
    # Fair-use demo rule: max two active/future approved or pending bookings per student.
    active_count = conn.execute("""SELECT COUNT(*) FROM bookings WHERE user_id=? AND status IN ('pending','approved','checked_in')""", (user["id"],)).fetchone()[0]
    if conflict:
        conn.close()
        flash("That time slot conflicts with another request or booking. Choose another slot.", "error")
        return redirect(url_for("resource_detail", resource_id=resource_id))
    if active_count >= 2:
        conn.close()
        flash("Fair-use limit reached: you may have at most two active requests/bookings at a time.", "error")
        return redirect(url_for("dashboard"))
    cur = conn.execute("""INSERT INTO bookings(resource_id,user_id,start_at,end_at,purpose,status,created_at)
        VALUES(?,?,?,?,?,'pending',?)""", (resource_id, user["id"], start_at.replace("T", " "), end_at.replace("T", " "), purpose, now()))
    bid = cur.lastrowid
    log_event(conn, user["name"], "BOOKING_REQUESTED", "booking", bid, f"Resource: {resource['name']}")
    conn.commit()
    conn.close()
    flash("Booking request submitted. The owner must review it.", "success")
    return redirect(url_for("dashboard"))

@app.route("/booking/<int:booking_id>/decision", methods=["POST"])
@login_required
@role_required("owner", "admin")
def booking_decision(booking_id):
    user = current_user()
    decision = request.form.get("decision")
    reason = request.form.get("reason", "").strip()
    if decision not in ("approved", "rejected", "waitlisted"):
        flash("Invalid decision.", "error")
        return redirect(url_for("dashboard"))
    conn = db()
    # Prevent two concurrent approvals from both passing the overlap check.
    conn.execute("BEGIN IMMEDIATE")
    booking = conn.execute("""SELECT b.*, r.name AS resource_name, r.owner_id FROM bookings b
        JOIN resources r ON r.id=b.resource_id WHERE b.id=?""", (booking_id,)).fetchone()
    if not booking:
        conn.close()
        flash("Booking not found.", "error")
        return redirect(url_for("dashboard"))
    if user["role"] != "admin" and booking["owner_id"] != user["id"]:
        conn.close()
        flash("You can only review requests for resources you own.", "error")
        return redirect(url_for("dashboard"))
    if booking["status"] != "pending":
        conn.close()
        flash("Only pending requests can be reviewed.", "error")
        return redirect(url_for("dashboard"))
    if decision == "approved":
        conflict = conn.execute("""SELECT id FROM bookings WHERE resource_id=? AND id<>? AND status IN ('approved','checked_in')
            AND start_at < ? AND end_at > ?""", (booking["resource_id"], booking_id, booking["end_at"], booking["start_at"])).fetchone()
        if conflict:
            conn.close()
            flash("Another booking now occupies that slot. Reject or waitlist this request instead.", "error")
            return redirect(url_for("dashboard"))
    if decision in ("rejected", "waitlisted") and not reason:
        reason = "Please contact the resource owner for details." if decision == "rejected" else "A competing request or limited capacity may affect this slot."
    conn.execute("UPDATE bookings SET status=?, decision_reason=? WHERE id=?", (decision, reason, booking_id))
    log_event(conn, user["name"], "BOOKING_" + decision.upper(), "booking", booking_id, reason)
    conn.commit()
    conn.close()
    flash(f"Booking {decision}.", "success")
    return redirect(url_for("dashboard"))

@app.route("/booking/<int:booking_id>/handoff", methods=["POST"])
@login_required
@role_required("student")
def handoff(booking_id):
    user = current_user()
    action = request.form.get("action")
    condition = request.form.get("condition", "Good")
    notes = request.form.get("notes", "").strip()
    conn = db()
    booking = conn.execute("SELECT * FROM bookings WHERE id=? AND user_id=?", (booking_id, user["id"])).fetchone()
    if not booking:
        conn.close()
        flash("Booking not found for your account.", "error")
        return redirect(url_for("dashboard"))
    if action == "checkin" and booking["status"] == "approved":
        conn.execute("UPDATE bookings SET status='checked_in', checked_in_at=? WHERE id=?", (now(), booking_id))
        conn.execute("""INSERT INTO condition_reports(booking_id,report_type,condition_label,notes,created_by,created_at)
            VALUES(?,'before',?,?,?,?)""", (booking_id, condition, notes, user["id"], now()))
        log_event(conn, user["name"], "CHECKED_IN", "booking", booking_id, f"Initial condition: {condition}; {notes}")
        flash("Check-in recorded.", "success")
    elif action == "checkout" and booking["status"] == "checked_in":
        conn.execute("UPDATE bookings SET status='returned', checked_out_at=? WHERE id=?", (now(), booking_id))
        conn.execute("""INSERT INTO condition_reports(booking_id,report_type,condition_label,notes,created_by,created_at)
            VALUES(?,'after',?,?,?,?)""", (booking_id, condition, notes, user["id"], now()))
        log_event(conn, user["name"], "RETURN_RECORDED", "booking", booking_id, f"Final condition: {condition}; {notes}")
        flash("Return recorded and transaction closed.", "success")
    else:
        conn.close()
        flash("That handover action is not valid for the current booking status.", "error")
        return redirect(url_for("dashboard"))
    conn.commit()
    conn.close()
    if action == "checkout" and condition.lower() in ("damaged", "faulty", "needs review"):
        return redirect(url_for("report_incident", booking_id=booking_id, suggested="damage"))
    return redirect(url_for("dashboard"))

@app.route("/booking/<int:booking_id>/incident", methods=["GET", "POST"])
@login_required
def report_incident(booking_id):
    user = current_user()
    conn = db()
    booking = conn.execute("""SELECT b.*, r.name AS resource_name, r.owner_id FROM bookings b
        JOIN resources r ON r.id=b.resource_id WHERE b.id=?""", (booking_id,)).fetchone()
    if not booking or (user["role"] == "student" and booking["user_id"] != user["id"]) or (user["role"] == "owner" and booking["owner_id"] != user["id"]):
        conn.close()
        flash("You don't have access to that booking.", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        kind = request.form.get("incident_type", "damage")
        description = request.form.get("description", "").strip()
        if kind not in ("damage", "delay", "scheduling", "safety", "other"):
            conn.close()
            flash("Choose a valid incident type.", "error")
            return redirect(url_for("report_incident", booking_id=booking_id))
        if not description:
            conn.close()
            flash("Please describe the incident.", "error")
            return redirect(url_for("report_incident", booking_id=booking_id))
        cur = conn.execute("""INSERT INTO incidents(booking_id,reporter_id,incident_type,description,created_at)
            VALUES(?,?,?,?,?)""", (booking_id, user["id"], kind, description, now()))
        iid = cur.lastrowid
        conn.execute("UPDATE resources SET available=0, condition_status='Needs review' WHERE id=?", (booking["resource_id"],)) if kind == "damage" else None
        log_event(conn, user["name"], "INCIDENT_REPORTED", "incident", iid, description)
        conn.commit()
        conn.close()
        flash("Incident recorded. The resource owner should review it.", "success")
        return redirect(url_for("dashboard"))
    conn.close()
    return render_template("incident.html", booking=booking, user=user)

@app.route("/audit")
@login_required
@role_required("owner", "admin")
def audit():
    user = current_user()
    conn = db()
    if user["role"] == "admin":
        events = conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 200").fetchall()
    else:
        events = conn.execute("""SELECT a.* FROM audit_events a
            LEFT JOIN bookings b ON a.entity_type='booking' AND a.entity_id=b.id
            LEFT JOIN resources r ON (a.entity_type='resource' AND a.entity_id=r.id) OR b.resource_id=r.id
            WHERE r.owner_id=? ORDER BY a.id DESC LIMIT 200""", (user["id"],)).fetchall()
    if user["role"] == "admin":
        incidents = conn.execute("""SELECT i.*, b.resource_id, r.name AS resource_name, p.name AS reporter_name
            FROM incidents i JOIN bookings b ON b.id=i.booking_id JOIN resources r ON r.id=b.resource_id
            JOIN profiles p ON p.id=i.reporter_id ORDER BY i.id DESC""").fetchall()
    else:
        # Owners should only see incidents involving resources they own.
        incidents = conn.execute("""SELECT i.*, b.resource_id, r.name AS resource_name, p.name AS reporter_name
            FROM incidents i JOIN bookings b ON b.id=i.booking_id JOIN resources r ON r.id=b.resource_id
            JOIN profiles p ON p.id=i.reporter_id
            WHERE r.owner_id=? ORDER BY i.id DESC""", (user["id"],)).fetchall()
    conn.close()
    return render_template("audit.html", events=events, incidents=incidents, user=user)

@app.route("/incident/<int:incident_id>/resolve", methods=["POST"])
@login_required
@role_required("owner", "admin")
def resolve_incident(incident_id):
    user = current_user()
    resolution = request.form.get("resolution", "").strip()
    if not resolution:
        flash("Add a resolution note first.", "error")
        return redirect(url_for("audit"))
    conn = db()
    incident = conn.execute("""SELECT i.*, r.owner_id, r.id AS resource_id FROM incidents i
        JOIN bookings b ON b.id=i.booking_id JOIN resources r ON r.id=b.resource_id WHERE i.id=?""", (incident_id,)).fetchone()
    if not incident or (user["role"] != "admin" and incident["owner_id"] != user["id"]):
        conn.close()
        flash("Incident not found or not authorized.", "error")
        return redirect(url_for("audit"))
    conn.execute("UPDATE incidents SET status='resolved', resolution=? WHERE id=?", (resolution, incident_id))
    # Do not mark a resource safe/available while another damage incident is still open.
    open_damage_count = conn.execute("""SELECT COUNT(*)
        FROM incidents i
        JOIN bookings b ON b.id=i.booking_id
        WHERE b.resource_id=? AND i.incident_type='damage' AND i.status='open' AND i.id<>?""",
        (incident["resource_id"], incident_id)).fetchone()[0]
    if open_damage_count == 0:
        conn.execute("UPDATE resources SET available=1, condition_status='Good' WHERE id=?", (incident["resource_id"],))
    log_event(conn, user["name"], "INCIDENT_RESOLVED", "incident", incident_id, resolution)
    conn.commit()
    conn.close()
    flash("Incident resolved. Resource marked available again.", "success")
    return redirect(url_for("audit"))

@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year}

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
