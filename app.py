import os
import random
import datetime
import uuid
from functools import wraps
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
from werkzeug.security import generate_password_hash, check_password_hash


# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

# Firebase configuration
FIREBASE_RTDB_URL = os.getenv(
    "FIREBASE_RTDB_URL", "https://randomizer-events-default-rtdb.asia-southeast1.firebasedatabase.app"
)
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET", "VvlSfG6dBnaj6KFZPSVkoARQ4MoPiITBqaP5N8Zc")

def get_firebase_url(path):
    """Helper to construct the Firebase REST URL with authentication."""
    if not path.startswith("/"):
        path = "/" + path
    return f"{FIREBASE_RTDB_URL}{path}.json?auth={FIREBASE_SECRET}"


def login_required(view_func):
    """Restrict a route to logged‑in admins only."""
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please log in as admin to access this page.", "warning")
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register/<event_id>", methods=["GET", "POST"])
def register(event_id):
    """Event specific registration form."""
    # Check if event exists
    event_url = get_firebase_url(f"/events/{event_id}")
    resp = requests.get(event_url)
    if resp.status_code != 200 or not resp.json():
        flash("Event not found or closed.", "danger")
        return redirect(url_for("index"))

    event_data = resp.json()
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile_number = request.form.get("mobile_number", "").strip()
        company_name = request.form.get("company_name", "").strip()
        position = request.form.get("position", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not all([name, mobile_number, company_name, position, email]):
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("register", event_id=event_id))

        # Check for duplicate email in this specific event
        url = get_firebase_url(f"/participants/{event_id}")
        resp = requests.get(url)
        all_participants = resp.json() if resp.status_code == 200 else {}
        if isinstance(all_participants, dict):
            for pid, pdata in all_participants.items():
                if pdata.get("email") == email:
                    flash("This email is already registered for this event.", "warning")
                    return redirect(url_for("register_success"))

        # Create new participant
        participant_data = {
            "name": name,
            "mobile_number": mobile_number,
            "company_name": company_name,
            "position": position,
            "email": email,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        post_url = get_firebase_url(f"/participants/{event_id}")
        requests.post(post_url, json=participant_data)

        return redirect(url_for("register_success"))

    return render_template("register.html", event=event_data, event_id=event_id)


@app.route("/success")
def register_success():
    return render_template("success.html")


@app.route("/admin/events/<event_id>/wheel")
@login_required
def wheel(event_id):
    event_url = get_firebase_url(f"/events/{event_id}")
    resp = requests.get(event_url)
    event_data = resp.json() or {}
    return render_template("wheel.html", event_id=event_id, event=event_data)


@app.route("/api/participants/<event_id>")
@login_required
def api_participants(event_id):
    url = get_firebase_url(f"/participants/{event_id}")
    resp = requests.get(url)
    data = resp.json() or {}
    
    participants = []
    if isinstance(data, dict):
        for pid, pdata in data.items():
            pdata["id"] = pid
            participants.append(pdata)
            
    participants.sort(key=lambda x: x.get("created_at", ""))
    return jsonify(participants)


@app.route("/api/random-winners/<event_id>")
@login_required
def api_random_winners(event_id):
    try:
        count = int(request.args.get("count", "1"))
    except ValueError:
        count = 1

    # Also avoid returning already-selected logic natively, but since this
    # replaces Server Side Draw, let's keep it behaving normally by returning random pool.
    url = get_firebase_url(f"/participants/{event_id}")
    resp = requests.get(url)
    data = resp.json() or {}
    
    participants = []
    if isinstance(data, dict):
        for pid, pdata in data.items():
            pdata["id"] = pid
            participants.append(pdata)

    if not participants:
        return jsonify({"winners": []})

    count = min(count, len(participants))
    winners = random.sample(participants, count)

    return jsonify({"winners": winners})


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_dashboard():
    if request.method == "POST":
        event_name = request.form.get("event_name", "").strip()
        if event_name:
            # Create Event
            event_data = {
                "name": event_name,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "admin_id": session.get("admin_id")
            }
            post_url = get_firebase_url("/events")
            requests.post(post_url, json=event_data)
            flash("Event created successfully.", "success")
            return redirect(url_for("admin_dashboard"))
            
    url = get_firebase_url("/events")
    resp = requests.get(url)
    data = resp.json() or {}
    
    events = []
    if isinstance(data, dict):
        for eid, edata in data.items():
            edata["id"] = eid
            events.append(edata)
        
    events.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return render_template("admin_dashboard.html", events=events)


@app.route("/admin/events/<event_id>", methods=["GET", "POST"])
@login_required
def admin_event_detail(event_id):
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile_number = request.form.get("mobile_number", "").strip()
        company_name = request.form.get("company_name", "").strip()
        position = request.form.get("position", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not all([name, mobile_number, company_name, position, email]):
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("admin_event_detail", event_id=event_id))

        url = get_firebase_url(f"/participants/{event_id}")
        resp = requests.get(url)
        all_participants = resp.json() if resp.status_code == 200 else {}
        if isinstance(all_participants, dict):
            for pid, pdata in all_participants.items():
                if pdata.get("email") == email:
                    flash("This email is already registered for this event.", "warning")
                    return redirect(url_for("admin_event_detail", event_id=event_id))

        participant_data = {
            "name": name,
            "mobile_number": mobile_number,
            "company_name": company_name,
            "position": position,
            "email": email,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        post_url = get_firebase_url(f"/participants/{event_id}")
        requests.post(post_url, json=participant_data)
        flash("Participant added manually.", "success")
        return redirect(url_for("admin_event_detail", event_id=event_id))

    event_url = get_firebase_url(f"/events/{event_id}")
    resp = requests.get(event_url)
    event_data = resp.json()
    if not event_data:
        flash("Event not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    event_data["id"] = event_id

    url = get_firebase_url(f"/participants/{event_id}")
    resp = requests.get(url)
    data = resp.json() or {}
    
    participants = []
    if isinstance(data, dict):
        for pid, pdata in data.items():
            pdata["id"] = pid
            participants.append(pdata)
            
    participants.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return render_template("event_detail.html", participants=participants, event=event_data)


@app.route("/admin/events/<event_id>/end", methods=["POST"])
@login_required
def end_event(event_id):
    # Wipe the participants for this event completely
    requests.delete(get_firebase_url(f"/participants/{event_id}"))
    # Wipe the event completely
    requests.delete(get_firebase_url(f"/events/{event_id}"))
    flash("Event and all its participants have been completely wiped and removed.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/events/<event_id>/participants/<participant_id>/delete", methods=["POST"])
@login_required
def delete_participant(event_id, participant_id):
    url = get_firebase_url(f"/participants/{event_id}/{participant_id}")
    requests.delete(url)
    flash("Participant deleted.", "success")
    return redirect(url_for("admin_event_detail", event_id=event_id))


@app.route("/admin/events/<event_id>/participants/<participant_id>/edit", methods=["GET", "POST"])
@login_required
def edit_participant(event_id, participant_id):
    url = get_firebase_url(f"/participants/{event_id}/{participant_id}")
    resp = requests.get(url)
    participant = resp.json()
    
    if not participant:
        flash("Participant not found.", "danger")
        return redirect(url_for("admin_event_detail", event_id=event_id))
        
    participant["id"] = participant_id

    if request.method == "POST":
        participant["name"] = request.form.get("name", "").strip()
        participant["mobile_number"] = request.form.get("mobile_number", "").strip()
        participant["company_name"] = request.form.get("company_name", "").strip()
        participant["position"] = request.form.get("position", "").strip()
        participant["email"] = request.form.get("email", "").strip().lower()

        if not all([
            participant["name"],
            participant["mobile_number"],
            participant["company_name"],
            participant["position"],
            participant["email"]
        ]):
            flash("All fields are required.", "danger")
            return redirect(url_for("edit_participant", event_id=event_id, participant_id=participant_id))

        put_url = get_firebase_url(f"/participants/{event_id}/{participant_id}")
        data_to_save = participant.copy()
        data_to_save.pop("id", None)
        requests.put(put_url, json=data_to_save)
        
        flash("Participant updated.", "success")
        return redirect(url_for("admin_event_detail", event_id=event_id))

    return render_template("edit_participant.html", participant=participant, event_id=event_id)


@app.route("/admin/signup", methods=["GET", "POST"])
def admin_signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        secret_code = request.form.get("secret_code", "").strip()

        if not all([email, password, confirm_password, secret_code]):
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("admin_signup"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("admin_signup"))

        expected_code = os.getenv("ADMIN_SECRET_CODE", "sltm@admin123")
        if secret_code != expected_code:
            flash("Invalid admin secret code.", "danger")
            return redirect(url_for("admin_signup"))

        url = get_firebase_url("/admin_users")
        resp = requests.get(url)
        all_admins = resp.json() if resp.status_code == 200 else {}
        if isinstance(all_admins, dict):
            for pid, pdata in all_admins.items():
                if pdata.get("email") == email:
                    flash("An admin with this email already exists.", "warning")
                    return redirect(url_for("admin_login"))

        admin_data = {
            "email": email,
            "password_hash": generate_password_hash(password),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        post_url = get_firebase_url("/admin_users")
        requests.post(post_url, json=admin_data)

        flash("Admin account created. You can now log in.", "success")
        return redirect(url_for("admin_login"))

    return render_template("admin_signup.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        url = get_firebase_url("/admin_users")
        resp = requests.get(url)
        all_admins = resp.json() if resp.status_code == 200 else {}
        
        admin_id = None
        admin_data = None
        if isinstance(all_admins, dict):
            for pid, pdata in all_admins.items():
                if pdata.get("email") == email:
                    admin_id = pid
                    admin_data = pdata
                    break
        
        if not admin_data:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("admin_login"))

        if not check_password_hash(admin_data.get("password_hash", ""), password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("admin_login"))

        session["admin_id"] = admin_id
        flash("Logged in successfully.", "success")

        next_url = request.args.get("next") or url_for("admin_dashboard")
        return redirect(next_url)

    return render_template("admin_login.html")


@app.route("/admin/logout")
@login_required
def admin_logout():
    session.pop("admin_id", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
