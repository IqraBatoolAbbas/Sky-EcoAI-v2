from functools import wraps
import csv
import io
import os
from flask import Flask, Response, jsonify, render_template, render_template_string, request, session, redirect, url_for
from route_agent import EcoRouteAgent
from auth_store import UserStore, ValidationError
from ledger_store import LedgerStore
from support_store import SupportStore
from admin_store import AdminStore, AdminAuthError
from fleet_store import FleetStore
from fleet_optimizer import FleetOptimizer
from disruption_agent import DisruptionAgent
from fleet_copilot import FleetCopilot
from rag_store import RagStore
from actor_util import current_actor
import html
import re
import secrets
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=30)
is_production = os.environ.get("FLASK_ENV", "").lower() == "production" or os.environ.get("SKY_ENV", "").lower() == "production"
configured_secret = os.environ.get("FLASK_SECRET_KEY")
if is_production and not configured_secret:
    raise RuntimeError("FLASK_SECRET_KEY must be set in production.")
app.secret_key = configured_secret or "sky-ecoai-hackathon-dev-secret-change-me"
app.config.update(
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=is_production,
)

agent = EcoRouteAgent()
users = UserStore()
ledger = LedgerStore()
support = SupportStore()
admin_store = AdminStore()
fleet_store = FleetStore()
fleet_optimizer = FleetOptimizer()
disruption_agent = DisruptionAgent(fleet_store)
rag_store = RagStore()
fleet_copilot = FleetCopilot(fleet_store, disruption_agent, rag_store)


@app.after_request
def add_security_headers(response):
    """Apply conservative browser protections without breaking the local demo."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(self), microphone=(self), camera=()")
    if request.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def login_required_api(fn):
    """Require session user (including demo guest) for mutating / private APIs."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Authentication required. Log in or use Demo Operator."}), 401
        return fn(*args, **kwargs)
    return wrapper


def sync_plan_flags(user):
    plan = (user or {}).get("plan", "free")
    session["is_premium"] = plan in {"premium", "pro"}
    session["is_pro"] = plan == "pro"


def refresh_session_user():
    user_context = session.get("user")
    email = (user_context or {}).get("email")
    if not email:
        return user_context

    user_list = users._read()
    for record in user_list:
        if record.get("email", "").strip().lower() == email.strip().lower():
            user_context = users._public(record)
            session["user"] = user_context
            sync_plan_flags(user_context)
            return user_context

    return user_context


def page_login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login_view", next=request.path))
        return view(*args, **kwargs)
    return wrapper



# Mock Class dynamic fallback layout sync check karne ke liye (Bina code delete kiye safe testing helper)
class MockUser:
    is_authenticated = True
    name = "Aiqra"
    initials = "AQ"
    email = "aiqra@example.com"
    plan = "free"

    # Python default string operations fallback for Jinja parsing syntax filter
    def __getitem__(self, key):
        return getattr(self, key, "")

    def get(self, key, default=None):
        return getattr(self, key, default)


# 🧭 Makes the logged-in user available to every template (nav, gated pages)
@app.context_processor
def inject_current_user():
    user_context = refresh_session_user()
    
    # 🚀 CHECK STATE: Agar user explicitly signup, login, ya home page par hai

    if request.path in ["/signup", "/login", "/", "/about"]:
        return {"current_user": user_context, "current_admin": session.get("admin")}
        
    # 💥 FORCED SAFETY DASHBOARD APP ACCELERATION LAYER:
    if not user_context and (request.path == "/dashboard" or request.path == "/workspace"):
        user_context = None
        
    return {"current_user": user_context, "current_admin": session.get("admin")}

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/workspace")
def workspace():
    if not session.get("user"):
        return redirect(url_for("login_view")) # Logout ke baad login par bhejo!
    return render_template("app_workspace.html")

@app.get("/control-tower")
def control_tower_view():
    if not session.get("user"):
        return redirect(url_for("login_view", next="/control-tower"))
    return render_template("control_tower.html")

@app.get("/control-tower/impact-print")
def control_tower_impact_print():
    if not session.get("user"):
        return redirect(url_for("login_view", next="/control-tower/impact-print"))
    summary = fleet_store.get_impact_summary()
    dash = fleet_store.get_dashboard()
    return render_template(
        "impact_print.html",
        summary=summary,
        dash=dash,
        actor=current_actor(),
        decisions=fleet_store.get_decisions()[-8:],
    )

@app.get("/dashboard")
def dashboard_view():
    if not session.get("user"):
        return redirect(url_for("login_view")) # Logout ke baad login par bhejo!
    return render_template("dashboard.html")

@app.get("/about")
def about_view():
    return render_template("about.html")


# ------------------------------------------------------------------
# 🔐 AUTH — PAGE ROUTES
# ------------------------------------------------------------------
@app.get("/login")
def login_view():
    if session.get("user"):
        return redirect(url_for("workspace"))
    return render_template("login.html")

@app.get("/signup")
def signup_view():
    if session.get("user"):
        return redirect(url_for("workspace"))
    return render_template("signup.html")

@app.get("/account")
def account_view():
    if not session.get("user"):
        return redirect(url_for("login_view", next="/account"))
    return render_template("account.html")

@app.get("/logout")
def logout_view():
    session.pop("user", None)
    session.pop("is_premium", None)
    session.pop("is_pro", None)
    return redirect(url_for("home"))

@app.get("/premium")
def premium_view():
    if not session.get("user"):
        return redirect(url_for("login_view", next="/premium"))
    current_user = refresh_session_user()
    plan = (current_user or {}).get("plan", "free")
    is_upgraded = plan in {"premium", "pro"}
    sync_plan_flags(current_user)
    return render_template("premium.html", current_user=current_user, is_upgraded=is_upgraded)

@app.get("/tickets")
def my_tickets_view():
    if not session.get("user"):
        return redirect(url_for("login_view", next="/tickets"))
    return render_template("my_tickets.html")


# ------------------------------------------------------------------
# 🔐 AUTH — API ROUTES
# ------------------------------------------------------------------
@app.post("/api/signup")
def api_signup():
    data = request.get_json(silent=True) or {}
    name = html.escape(data.get("name", "").strip())
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    try:
        user = users.create_user(name, email, password)
        session["user"] = user
        sync_plan_flags(user)
        return jsonify(user), 201
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        app.logger.exception("Signup failed")
        return jsonify({"error": "Signup is temporarily unavailable. Please try again."}), 500

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    try:
        user = users.verify_user(email, password)
        session["user"] = user
        sync_plan_flags(user)
        session.permanent = True
        return jsonify(user), 200
    except ValidationError as e:
        return jsonify({"error": str(e)}), 401
    except Exception:
        app.logger.exception("Login failed")
        return jsonify({"error": "Login is temporarily unavailable. Please try again."}), 500


@app.post("/api/demo-login")
def api_demo_login():
    """Hackathon fast-path: session without signup."""
    user = {
        "name": "Demo Operator",
        "email": "demo@sky-ecoai.local",
        "initials": "DO",
        "plan": "pro",
        "is_demo": True,
    }
    session["user"] = user
    session["is_premium"] = True
    session["is_pro"] = True
    session.permanent = True
    return jsonify({"user": user, "redirect": "/control-tower"}), 200

@app.post("/api/logout")
def api_logout():
    session.pop("user", None)
    session.pop("is_premium", None)
    session.pop("is_pro", None)
    return jsonify({"ok": True})

@app.get("/api/session")
def api_session():
    return jsonify({"user": session.get("user")})

@app.post("/api/account")
def api_update_account():
    if not session.get("user"):
        return jsonify({"error": "You must be logged in to update account settings."}), 401

    data = request.get_json(silent=True) or {}
    
    update_payload = {}
    if data.get("name"):
        update_payload["name"] = html.escape(data.get("name").strip())
    if data.get("preferences"):
        update_payload["preferences"] = data.get("preferences")

    try:
        # Try updating in the store
        user = users.update_user(session["user"]["email"], update_payload)
        session["user"] = user
        sync_plan_flags(user)
        session.modified = True
        return jsonify(user), 200
    except ValidationError as e:
        
        if "User not found" in str(e):
            current_user = session["user"]
            if "name" in update_payload:
                current_user["name"] = update_payload["name"]
                # Initials update karne ke liye
                parts = [p for p in update_payload["name"].split(" ") if p]
                current_user["initials"] = (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else update_payload["name"][:2].upper()
            if "preferences" in update_payload:
                current_user["preferences"] = update_payload["preferences"]
            
            session["user"] = current_user
            session.modified = True
            return jsonify(current_user), 200
            
        return jsonify({"error": str(e)}), 400
    except Exception:
        app.logger.exception("Account update failed")
        return jsonify({"error": "Account settings could not be updated."}), 500
# ------------------------------------------------------------------
# 📒 PER-ACCOUNT LEDGER (Persisted Server-Side)
# ------------------------------------------------------------------
@app.get("/api/ledger")
def api_get_ledger():
    if not session.get("user"):
        return jsonify({"error": "Log in to view your saved ledger."}), 401
    return jsonify({"entries": ledger.get_entries(session["user"]["email"])})

@app.post("/api/ledger")
def api_add_ledger_entry():
    if not session.get("user"):
        return jsonify({"error": "Log in to save this trip to your ledger."}), 401
    data = request.get_json(silent=True) or {}
    try:
        record = ledger.add_entry(session["user"]["email"], data)
        return jsonify(record), 201
    except Exception as e:
        return jsonify({"error": f"Ledger Write Error: {str(e)}"}), 500

@app.post("/api/ledger/favorite")
def api_toggle_favorite():
    if not session.get("user"):
        return jsonify({"error": "Log in to save favorites."}), 401
    data = request.get_json(silent=True) or {}
    try:
        record = ledger.toggle_favorite(session["user"]["email"], data.get("id"))
        return jsonify(record), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Favorite Toggle Error: {str(e)}"}), 500

@app.delete("/api/ledger")
def api_clear_ledger():
    if not session.get("user"):
        return jsonify({"error": "Log in to manage your ledger."}), 401
    ledger.clear(session["user"]["email"])
    return jsonify({"ok": True})


# ------------------------------------------------------------------
# 🎫 SUPPORT TICKETS (Unified Processing Engine with Instant AI)
# ------------------------------------------------------------------
@app.post("/api/support/ticket", endpoint="api_create_support_ticket")
def api_create_support_ticket():
    data = request.get_json(silent=True) or {}
    email = html.escape(data.get("email", "").strip())
    category = html.escape(data.get("category", "").strip())
    message = html.escape(data.get("message", "").strip())

    if not email or not message:
        return jsonify({"error": "Validation Error: Email and message are required."}), 400
    if len(email) > 254 or len(category) > 60 or len(message) > 5000:
        return jsonify({"error": "Ticket fields exceed the allowed length."}), 400

    try:
        # 1. Store the baseline ticket structure
        ticket = support.create_ticket(email, category, message)
        ticket_id = ticket.get("ticket_id") if isinstance(ticket, dict) else getattr(ticket, "ticket_id", None)
        
        ai_reply = "Sky.EcoAI Copilot: Thank you for your dispatch! Our system has cataloged your inquiry, and an administrator will review this shortly."
        
        # 2. Fire Generative Agent Optimization Check
        try:
            ai_raw_reply = agent.optimize(category, message, "eco-ai-bot")
            if isinstance(ai_raw_reply, dict) and ai_raw_reply.get("report"):
                ai_reply = ai_raw_reply.get("report")
            elif isinstance(ai_raw_reply, str) and ai_raw_reply.strip():
                ai_reply = ai_raw_reply
        except Exception as ai_err:
            print(f"⚠️ AI Autocall Notice: {str(ai_err)}")

        # 3. Inject AI payload into ticket architecture
        if ticket_id:
            ticket = support.respond(ticket_id, f"🤖 [AI Assistant]: {ai_reply}")
            if isinstance(ticket, dict):
                ticket["status"] = "ai-responded"

        return jsonify({
            "success": True, 
            "message": "Ticket successfully dispatched to engineering desk.",
            "ai_response": ai_reply,
            "ticket": ticket
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"\n❌ CLIENT TICKET CREATION CRASH: {str(e)}\n")
        return jsonify({"error": f"Support Engine Error: {str(e)}"}), 500


# 🔗 NEW: Added missing endpoint for active user sessions to fetch history tabs
@app.get("/api/my-tickets")
def api_get_user_tickets():
    # Regular user context checkout, checks email directly
    current_user = session.get("user")
    if not current_user or not current_user.get("email"):
        return jsonify({"error": "Authentication Required: Log in to fetch history logs."}), 401
    
    try:
        all_tickets = support.list_all() or []
        user_email = current_user["email"].strip().lower()
        
        # Filter tickets matching logged-in account identity
        filtered_tickets = []
        for t in all_tickets:
            t_email = t.get("email", "").strip().lower() if isinstance(t, dict) else getattr(t, "email", "").strip().lower()
            if t_email == user_email:
                filtered_tickets.append(t)
                
        return jsonify({"tickets": filtered_tickets}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve ticket history matrix: {str(e)}"}), 500


# ------------------------------------------------------------------
# 💳 PREMIUM UPGRADE (Simulated Payment Gateway Architecture)
# ------------------------------------------------------------------
CARD_NUMBER_PATTERN = re.compile(r"^\d{13,19}$")
EXPIRY_PATTERN = re.compile(r"^(0[1-9]|1[0-2])\/?([0-9]{2})$")

@app.post("/api/premium/checkout")
def api_premium_checkout():
    if not session.get("user"):
        return jsonify({"error": "Log in to upgrade to Premium."}), 401

    data = request.get_json(silent=True) or {}
    card_number = re.sub(r"\s+", "", data.get("card_number", ""))
    expiry = data.get("expiry", "").strip()
    cvv = data.get("cvv", "").strip()
    name_on_card = data.get("name_on_card", "").strip()
    
    # 🚀 NEW: Check which tier user selected (default is premium)
    target_plan = data.get("plan_type", "premium").lower() 

    if not name_on_card or len(name_on_card) < 2:
        return jsonify({"error": "Enter the name exactly as it appears on the card."}), 400
    if not CARD_NUMBER_PATTERN.match(card_number):
        return jsonify({"error": "Enter a valid card number (13–19 digits)."}), 400
    match = EXPIRY_PATTERN.match(expiry)
    if not match:
        return jsonify({"error": "Enter the expiry date as MM/YY."}), 400
    if not re.match(r"^\d{3,4}$", cvv):
        return jsonify({"error": "Enter a valid CVV."}), 400
    expiry_month, expiry_year = int(match.group(1)), 2000 + int(match.group(2))
    now = datetime.now(timezone.utc)
    if (expiry_year, expiry_month) < (now.year, now.month):
        return jsonify({"error": "This card has expired."}), 400

    try:
        # 1. User records ko DB/Storage mein upgrade karein
        user = users.upgrade_to_premium(session["user"]["email"], card_number[-4:], target_plan)
            
        session["user"] = user
            
        # 💥 DYNAMIC TIER INITIALIZATION MATRIX
        if target_plan == "pro":
            session["is_premium"] = True
            session["is_pro"] = True
            plan_label = "Pro 🚀"
        else:
            session["is_premium"] = True
            session["is_pro"] = False
            plan_label = "Premium 👑"
        
        return jsonify({
            "status": "success",
            "message": f"Payment complete — welcome to {plan_label}!",
            "user": user
        }), 200

    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Checkout Error: {str(e)}"}), 500


# ------------------------------------------------------------------
# 🛠️ ADMIN — SEPARATE CREDENTIAL SPACE & CONTROL MODULES
# ------------------------------------------------------------------
@app.get("/admin/login")
def admin_login_view():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard_view"))
    return render_template("admin_login.html")

@app.post("/api/admin/login")
def api_admin_login():
    data = request.get_json(silent=True) or {}
    try:
        admin = admin_store.verify_admin(data.get("email", ""), data.get("password", ""))
        session["admin"] = admin
        session["is_admin"] = True
        session.permanent = True
        return jsonify(admin), 200
    except AdminAuthError as e:
        return jsonify({"error": str(e)}), 401

def admin_required():
    return session.get("admin") is not None or session.get("is_admin") is True

@app.get("/admin/logout")
def admin_logout_view():
    session.pop("admin", None)
    session.pop("is_admin", None)
    return redirect(url_for("admin_login_view"))

@app.get("/admin")
def admin_dashboard_view():
    if not admin_required():
        return redirect(url_for("admin_login_view"))
    return render_template("admin_dashboard.html")

@app.get("/api/admin/overview")
def api_admin_overview():
    if not admin_required():
        return jsonify({"error": "Admin session required."}), 401
    
    try:
        all_users = users.list_all_users() or []
        all_tickets = support.list_all() or []
        
        total_users = len(all_users)
        
        premium_users = 0
        for u in all_users:
            if isinstance(u, dict) and u.get("plan") == "premium":
                premium_users += 1
            elif hasattr(u, "plan") and getattr(u, "plan") == "premium":
                premium_users += 1

        open_tickets = 0
        for t in all_tickets:
            if isinstance(t, dict) and t.get("status") == "open":
                open_tickets += 1
            elif hasattr(t, "status") and getattr(t, "status") == "open":
                open_tickets += 1

        return jsonify({
            "users": all_users if isinstance(all_users, list) else [],
            "tickets": all_tickets if isinstance(all_tickets, list) else [],
            "stats": {
                "total_users": total_users,
                "premium_users": premium_users,
                "open_tickets": open_tickets,
                "total_tickets": len(all_tickets),
            },
        }), 200

    except Exception as e:
        print(f"\n❌ CRITICAL ADMIN DASHBOARD CRASH: {str(e)}\n")
        return jsonify({"error": f"Internal Data Processing Error: {str(e)}"}), 500


@app.route("/api/admin/tickets/<path:ticket_id>/respond", methods=["POST"])
def api_admin_respond_ticket(ticket_id):
    if not admin_required():
        return jsonify({"error": "Admin session required."}), 401
        
    data = request.get_json(silent=True) or {}
    response_text = data.get("response", "").strip()
    
    if not response_text:
        return jsonify({"error": "Validation Error: Response message cannot be empty."}), 400
        
    try:
        ticket = support.respond(ticket_id, html.escape(response_text))
        return jsonify(ticket), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"\n❌ TICKET DISPATCH RESPOND CRASH: {str(e)}\n")
        return jsonify({"error": f"Admin Response Error: {str(e)}"}), 500


# ------------------------------------------------------------------
# 🏗️ FLEET CONTROL TOWER — Hackathon MVP APIs
# ------------------------------------------------------------------
@app.get("/api/fleet/dashboard")
@login_required_api
def api_fleet_dashboard():
    return jsonify(fleet_store.get_dashboard())

@app.get("/api/fleet/vehicles")
@login_required_api
def api_fleet_vehicles():
    return jsonify({"vehicles": fleet_store.list_vehicles()})

@app.post("/api/fleet/vehicles")
@login_required_api
def api_fleet_create_vehicle():
    data = request.get_json(silent=True) or {}
    try:
        vehicle = fleet_store.add_vehicle(data)
        return jsonify(vehicle), 201
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

@app.get("/api/fleet/orders")
@login_required_api
def api_fleet_orders():
    return jsonify({"orders": fleet_store.list_orders()})

@app.post("/api/fleet/orders")
@login_required_api
def api_fleet_create_order():
    data = request.get_json(silent=True) or {}
    if "lat" not in data or "lng" not in data:
        return jsonify({"error": "lat and lng are required."}), 400
    try:
        order = fleet_store.add_order(data)
        return jsonify(order), 201
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

@app.get("/api/fleet/state")
@login_required_api
def api_fleet_state():
    return jsonify(fleet_store.get_state())

@app.post("/api/fleet/optimize")
@login_required_api
def api_fleet_optimize():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "all")
    if mode not in {"all", "economy", "green", "service"}:
        return jsonify({"error": "mode must be one of: all, economy, green, service."}), 400
    state = fleet_store.get_state()
    budget = float(state.get("carbon_budget_kg") or 45)
    enforce = bool(state.get("enforce_carbon_budget", True))
    if mode == "all":
        plans = fleet_optimizer.generate_all_modes(state["depot"], state["vehicles"], state["orders"])
        ranked = fleet_optimizer.compare_plans(plans)
    else:
        ranked = [fleet_optimizer.optimize_fleet(state["depot"], state["vehicles"], state["orders"], mode=mode)]

    for p in ranked:
        co2 = float(p.get("total_co2_kg") or 0)
        p["within_carbon_budget"] = co2 <= budget
        p["carbon_budget_kg"] = budget
        comparison_score = float(p.get("comparison_score", p.get("score", 0)))
        if enforce and not p["within_carbon_budget"]:
            comparison_score += 5000
            p["budget_penalty"] = True
        p["comparison_score"] = round(comparison_score, 2)
        p["score"] = p["comparison_score"]
    mode_tiebreaker = {"green": 0, "economy": 1, "service": 2}
    ranked = sorted(
        ranked,
        key=lambda x: (
            len(x.get("unassigned_orders", [])),
            x.get("comparison_score", float("inf")),
            mode_tiebreaker.get(x.get("mode"), 9),
        ),
    )
    for i, p in enumerate(ranked):
        p["rank"] = i + 1

    fleet_store.set_candidate_plans(ranked)
    if ranked:
        fleet_store.log_decision(
            trigger="optimize",
            alternatives=[{k: p.get(k) for k in ("id", "mode", "label", "score", "total_co2_kg", "total_operating_cost_pkr", "within_carbon_budget")} for p in ranked],
            selected=ranked[0],
            explanation=f"Generated {len(ranked)} plan(s); recommended {ranked[0].get('label')} (carbon enforce={enforce}).",
        )
    fleet_store.log_activity(
        current_actor(),
        "optimize",
        f"Generated {len(ranked)} plan(s); recommended {ranked[0].get('label') if ranked else 'none'}",
    )
    return jsonify({
        "plans": ranked,
        "recommended_plan_id": ranked[0]["id"] if ranked else None,
        "carbon_budget_kg": budget,
        "enforce_carbon_budget": enforce,
    })


@app.post("/api/fleet/plans/<plan_id>/apply")
@login_required_api
def api_fleet_apply_plan(plan_id):
    try:
        plan = fleet_store.apply_plan(plan_id)
        fleet_store.log_decision(
            trigger="plan_applied",
            alternatives=[],
            selected=plan,
            explanation=f"Operator applied {plan.get('label', plan_id)}.",
            approval_status="approved",
        )
        fleet_store.log_activity(current_actor(), "apply_plan", f"Applied {plan.get('label', plan_id)}")
        return jsonify(plan)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

@app.post("/api/fleet/events")
@login_required_api
def api_fleet_events():
    data = request.get_json(silent=True) or {}
    event_type = data.get("type", "").strip().lower()
    try:
        if event_type == "breakdown":
            result = disruption_agent.simulate_breakdown(data.get("vehicle_id"))
        elif event_type == "urgent_order":
            result = disruption_agent.insert_urgent_order(data)
        elif event_type == "road_blockage":
            result = disruption_agent.apply_road_penalty(
                float(data["lat"]), float(data["lng"]), float(data.get("radius_km", 2.0))
            )
        elif event_type == "range_warning":
            result = disruption_agent.simulate_range_warning(data.get("vehicle_id", "V6"))
        else:
            return jsonify({"error": f"Unknown event type: {event_type}"}), 400
        from genai_services import generate_ops_alert
        fleet_store.push_alert(generate_ops_alert(event_type, str(result)[:120]))
        fleet_store.log_activity(current_actor(), f"event:{event_type}", str(result)[:180])
        return jsonify(result), 201
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

@app.post("/api/fleet/recovery")
@login_required_api
def api_fleet_recovery():
    data = request.get_json(silent=True) or {}
    trigger = data.get("trigger", "disruption")
    auto_apply = bool(data.get("auto_apply", False))
    result = disruption_agent.generate_recovery_plans(trigger)
    if auto_apply and result.get("recommended_plan_id"):
        applied = disruption_agent.apply_recovery_plan(result["recommended_plan_id"], auto=True)
        result["applied"] = applied
        from genai_services import generate_ops_alert
        fleet_store.push_alert(generate_ops_alert("recovery_applied", result.get("explanation", "")))
    fleet_store.log_activity(
        current_actor(),
        "recovery",
        f"trigger={trigger}; auto={auto_apply}; recommended={result.get('recommended_plan_id')}",
    )
    return jsonify(result)

@app.get("/api/fleet/decisions")
@login_required_api
def api_fleet_decisions():
    return jsonify({"decisions": fleet_store.get_decisions()})

@app.get("/api/fleet/impact")
@login_required_api
def api_fleet_impact():
    return jsonify(fleet_store.get_impact_summary())

@app.post("/api/fleet/copilot")
@login_required_api
def api_fleet_copilot():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "message is required."}), 400
    if len(message) > 2000:
        return jsonify({"error": "message must be 2,000 characters or fewer."}), 400
    confirm = bool(data.get("confirm", False))
    pending_action = data.get("pending_action")
    return jsonify(fleet_copilot.process_message(
        message, confirm_action=confirm, pending_action=pending_action, allow_mutations=True
    ))

@app.post("/api/fleet/reset-demo")
@login_required_api
def api_fleet_reset_demo():
    state = fleet_store.reset_demo()
    fleet_store.log_activity(current_actor(), "reset_demo", "Restored Lahore seed scenario")
    return jsonify({"ok": True, "message": "Demo scenario reset.", "depot": state.get("depot")})


@app.post("/api/fleet/scenarios")
@login_required_api
def api_fleet_scenarios():
    data = request.get_json(silent=True) or {}
    scenario = data.get("scenario", "").strip()
    if not scenario:
        return jsonify({
            "error": "scenario is required",
            "available": ["medical_rush", "carbon_budget_breach", "ev_low_range"],
        }), 400
    try:
        result = disruption_agent.run_scenario(scenario)
        fleet_store.log_activity(current_actor(), "scenario", result.get("title") or scenario)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/fleet/delta")
@login_required_api
def api_fleet_delta():
    return jsonify({"delta": fleet_store.get_latest_delta(), "baseline": fleet_store.get_state().get("baseline_snapshot")})


@app.get("/api/fleet/activity")
@login_required_api
def api_fleet_activity():
    return jsonify({"activity": fleet_store.get_dashboard().get("activity_log", [])})


@app.post("/api/fleet/scenario/nl")
@login_required_api
def api_fleet_scenario_nl():
    """Natural-language scenario generation (GenAI intent → tools)."""
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or data.get("message") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required", "example": "Two medical emergencies near Cantt then breakdown"}), 400
    if len(prompt) > 2000:
        return jsonify({"error": "prompt must be 2,000 characters or fewer."}), 400
    auto_recover = bool(data.get("auto_recover", True))
    result = disruption_agent.execute_nl_scenario(prompt)
    if auto_recover and result.get("recovery") and result["recovery"].get("recommended_plan_id"):
        if data.get("auto_apply"):
            applied = disruption_agent.apply_recovery_plan(result["recovery"]["recommended_plan_id"], auto=True)
            result["applied"] = applied
    fleet_store.log_activity(current_actor(), "nl_scenario", prompt[:160])
    return jsonify(result), 201


@app.get("/api/fleet/impact/narrative")
@login_required_api
def api_fleet_impact_narrative():
    from genai_services import generate_impact_narrative

    summary = fleet_store.get_impact_summary()
    narrative = generate_impact_narrative(summary, fleet_store.get_decisions())
    return jsonify({"summary": summary, **narrative})


@app.get("/api/fleet/alerts")
@login_required_api
def api_fleet_alerts():
    return jsonify({"alerts": fleet_store.list_alerts()})


@app.post("/api/fleet/carbon-enforcement")
@login_required_api
def api_fleet_carbon_enforcement():
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", True))
    val = fleet_store.set_carbon_enforcement(enabled)
    fleet_store.log_activity(current_actor(), "carbon_enforcement", f"enabled={val}")
    return jsonify({"enforce_carbon_budget": val})


@app.post("/api/help/chat")
def api_help_chat():
    """Floating Sky Assistant — public RAG Q&A (read-only)."""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "message is required."}), 400
    if len(message) > 2000:
        return jsonify({"error": "message must be 2,000 characters or fewer."}), 400
    return jsonify(fleet_copilot.answer_help(message))


@app.get("/api/help/sources")
def api_help_sources():
    return jsonify({"chunks": rag_store.reload(), "knowledge_dir": "knowledge/"})


# ------------------------------------------------------------------
# 🌱 ROUTE OPTIMIZATION TERMINAL
# ------------------------------------------------------------------
@app.post("/api/optimize")
@login_required_api
def optimize_route():
    data = request.get_json(silent=True) or {}
    source = html.escape(data.get("source", "").strip())
    destination = html.escape(data.get("destination", "").strip())
    vehicle = data.get("vehicle", "").strip().lower()
    
    # 🚀 OPTIONAL SECURITY MATRIX:
    is_batch_request = data.get("is_batch", False)
    if is_batch_request and not session.get("is_pro"):
        return jsonify({"error": "Batch route simulation requires Professional Grid Suite (Pro)."}), 403

    if not source or not destination:
        return jsonify({"error": "Validation Error: Inputs cannot be empty."}), 400
    if len(source) > 200 or len(destination) > 200:
        return jsonify({"error": "Source and destination must be 200 characters or fewer."}), 400

    try:
        report_output = agent.optimize(source, destination, vehicle)
        return jsonify(report_output)
    except Exception:
        app.logger.exception("Route optimization failed")
        return jsonify({"error": "Route optimization failed. Please try again."}), 500
    
@app.route('/admin/reply/<ticket_id>', methods=['POST'])
def admin_reply(ticket_id):
    # Admin session check (Security)
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 403
    
    reply_text = (request.form.get("reply") or "").strip()
    try:
        return jsonify(support.respond(ticket_id, html.escape(reply_text))), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/admin/users/<path:user_id>/delete", methods=["DELETE", "POST"])
def api_admin_delete_user(user_id):
    if not admin_required():
        return jsonify({"error": "Admin session required."}), 401
        
    try:
        users.delete_user(user_id)
        return jsonify({"message": "Account permanently deleted."}), 200
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception:
        app.logger.exception("Admin user deletion failed")
        return jsonify({"error": "Account could not be deleted."}), 500

@app.route("/api/auth/logout", methods=["POST", "GET"])
def user_logout():
    # User ki sari session variables ko clear kar dein
    session.clear() 
    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


@app.route("/api/export/csv")
def api_export_csv():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Session aur Database plan check karein
    is_premium = session.get("is_premium", False)
    plan = user.get("plan", "free")
    
    try:
        # Ledger store ka method call karein
        entries = ledger.get_premium_csv_data(user["email"], is_premium, plan)
        
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Query", "Engine", "Sprint CO2(g)", "Green CO2(g)", "Saved CO2(g)"])
        for entry in entries:
            row = [entry.get("query", ""), entry.get("engine", ""), entry.get("sprintCo2", ""), entry.get("greenCo2", ""), entry.get("saved", "")]
            writer.writerow([f"'{value}" if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for value in row])
        
        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=sky_eco_telemetry.csv"}
        )
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception:
        app.logger.exception("CSV export failed")
        return jsonify({"error": "CSV export failed."}), 500
@app.route('/update_profile', methods=['POST'])
def update_profile():
    try:
        user_session = session.get("user")
        if not user_session:
            return jsonify({"error": "No session found"}), 401
        
        user_email = user_session["email"]
        updated_user = users.update_user(user_email, {"name": request.form.get("name", "").strip()})
        session["user"] = updated_user
        sync_plan_flags(updated_user)
        session.modified = True
        return jsonify({"success": True, "user": updated_user})
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Profile update failed")
        return jsonify({"error": "Profile could not be updated."}), 500

@app.route('/api/agent/predict', methods=['GET'])
def get_agent_prediction():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    email = user.get("email", "").strip().lower()
    user_entries = ledger.get_entries(email)
    
    if not user_entries:
        return jsonify({"status": "waiting"})
        
    total_saved = sum(float(entry.get('saved', 0)) for entry in user_entries)
    
    # E-commerce style gallery data
    gallery_data = [
        {"id": 1, "title": "Route Optimization", "desc": "Switch to green path to save CO2.", "img": "static/images/route.jpg", "saved": "2,299g"},
        {"id": 2, "title": "Fleet Upgrade", "desc": "Switch to Electric for max impact.", "img": "static/images/electric.jpg", "saved": "5,000g"},
        {"id": 3, "title": "Fleet Maintenance", "desc": "Regular checkups reduce emissions.", "img": "static/images/maint.jpg", "saved": "1,500g"}
    ]
    
    return jsonify({
        "status": "ready",
        "total_saved": total_saved,
        "recommendation": f"Current savings: {total_saved}g. Scale your target to 35,000g.",
        "recommendations": gallery_data
    })

# 1. Page load karne ke liye (Browser ke liye)
@app.route('/checkout')
def checkout_page():
    if not session.get("user"):
        return redirect(url_for("login_view", next="/checkout"))
    return render_template('premium.html')
@app.route('/contact-sales')
def contact_sales():
    return render_template('contact_sales.html')   

@app.route('/api/analyze-fleet', methods=['POST'])
def analyze_fleet():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "message is required."}), 400
    if len(message) > 2000:
        return jsonify({"error": "message must be 2,000 characters or fewer."}), 400
    
    # 2. Variable define karein (Yehi missing tha!)
    # agent.optimize aapka original function hai
    try:
        analysis_result = agent.optimize("Diagnostic", message, "eco-ai-bot")
    except Exception:
        app.logger.exception("Fleet analysis failed")
        return jsonify({"error": "Fleet analysis failed. Please try again."}), 500
    
    # 3. Ab 'analysis_result' defined hai, so hum return kar sakte hain
    return jsonify({
        "success": True,
        "prediction": {
            "carbon": "14%", 
            "fuel": "9%"
        },
        "report": analysis_result
    })


@app.route('/debug-routes')
@login_required_api
def debug_routes():
    if not app.debug:
        return jsonify({"error": "Not found."}), 404
    output = []
    for rule in app.url_map.iter_rules():
        output.append(f"{rule.endpoint}: {rule.rule}")
    return "<br>".join(output)
@app.route('/carbon-agent')
def carbon_agent():
    if not session.get("user"):
        return redirect(url_for("login_view"))
    return render_template("carbon_agent.html")
# ------------------------------------------------------------------
# 🚧 ERROR HANDLERS
# ------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=debug_enabled, use_reloader=False)
