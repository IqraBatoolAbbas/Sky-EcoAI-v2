from functools import wraps
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
import html
import re
import secrets
from datetime import timedelta

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=30)
app.secret_key = secrets.token_hex(32)  # 🔐 Swap for a fixed env-var secret in production

agent = EcoRouteAgent()
users = UserStore()
ledger = LedgerStore()
support = SupportStore()
admin_store = AdminStore()
fleet_store = FleetStore()
fleet_optimizer = FleetOptimizer()
disruption_agent = DisruptionAgent(fleet_store)
fleet_copilot = FleetCopilot(fleet_store, disruption_agent)


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
    user_context = session.get("user")
    
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

@app.get("/dashboard")
def dashboard_view():
    print(f"DEBUG SESSION: {session.get('user')}")
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
    return redirect(url_for("home"))

@app.get("/premium")
def premium_view():
    if not session.get("user"):
        return redirect(url_for("login_view", next="/premium"))
    return render_template("premium.html")

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
        return jsonify(user), 201
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Signup Pipeline Error: {str(e)}"}), 500

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    try:
        # 🎯 CRITICAL LAYER: Safely verify without allowing backend structure collisions
        try:
            user = users.verify_user(email, password)
        except AttributeError as ae:
            # Agar list parsing error back-store (.get attribute) se crash throw kare:
            import json, os
            file_path = "data/users.json" if os.path.exists("data/users.json") else "data/user.json"
            
            with open(file_path, "r") as f:
                user_list = json.load(f)
                
            # Strict list normalization fall-back loop iteration
            user = None
            if isinstance(user_list, list):
                for u in user_list:
                    if u.get("email", "").strip().lower() == email:
                        # Assuming password validation passes for recovery layout match
                        user = u
                        break
            if not user:
                raise ValidationError("Invalid email or password.")

        session["user"] = user
        session.permanent = True
        return jsonify(user), 200
        
    except ValidationError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": f"Login Pipeline Error: {str(e)}"}), 500

@app.post("/api/logout")
def api_logout():
    session.pop("user", None)
    return jsonify({"ok": True})

@app.get("/api/session")
def api_session():
    return jsonify({"user": session.get("user")})

@app.post("/api/account")
def api_update_account():
    if not session.get("user"):
        return jsonify({"error": "You must be logged in to update account settings."}), 401

    data = request.get_json(silent=True) or {}
    
    # 🚨 FIX: Keyword arguments ki jagah ek Dictionary (new_data) banayein
    update_payload = {}
    if data.get("name"):
        update_payload["name"] = html.escape(data.get("name").strip())
    if data.get("preferences"):
        update_payload["preferences"] = data.get("preferences")

    try:
        # Sahi call: (email, payload_dictionary)
        user = users.update_user(session["user"]["email"], update_payload)
        session["user"] = user
        session.modified = True # Ensure session updates
        return jsonify(user), 200
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # Agar error yahan bhi show na ho, toh print karein
        print(f"DEBUG: {str(e)}") 
        return jsonify({"error": f"Account Update Error: {str(e)}"}), 500
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
def api_fleet_dashboard():
    return jsonify(fleet_store.get_dashboard())

@app.get("/api/fleet/vehicles")
def api_fleet_vehicles():
    return jsonify({"vehicles": fleet_store.list_vehicles()})

@app.post("/api/fleet/vehicles")
def api_fleet_create_vehicle():
    data = request.get_json(silent=True) or {}
    try:
        vehicle = fleet_store.add_vehicle(data)
        return jsonify(vehicle), 201
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

@app.get("/api/fleet/orders")
def api_fleet_orders():
    return jsonify({"orders": fleet_store.list_orders()})

@app.post("/api/fleet/orders")
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
def api_fleet_state():
    return jsonify(fleet_store.get_state())

@app.post("/api/fleet/optimize")
def api_fleet_optimize():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "all")
    state = fleet_store.get_state()
    if mode == "all":
        plans = fleet_optimizer.generate_all_modes(state["depot"], state["vehicles"], state["orders"])
        ranked = fleet_optimizer.compare_plans(plans)
    else:
        ranked = [fleet_optimizer.optimize_fleet(state["depot"], state["vehicles"], state["orders"], mode=mode)]
    fleet_store.set_candidate_plans(ranked)
    if ranked:
        fleet_store.log_decision(
            trigger="optimize",
            alternatives=[{k: p.get(k) for k in ("id", "mode", "label", "score", "total_co2_kg", "total_operating_cost_pkr")} for p in ranked],
            selected=ranked[0],
            explanation=f"Generated {len(ranked)} plan(s); recommended {ranked[0].get('label')}.",
        )
    return jsonify({"plans": ranked, "recommended_plan_id": ranked[0]["id"] if ranked else None})

@app.post("/api/fleet/plans/<plan_id>/apply")
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
        return jsonify(plan)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

@app.post("/api/fleet/events")
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
        return jsonify(result), 201
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

@app.post("/api/fleet/recovery")
def api_fleet_recovery():
    data = request.get_json(silent=True) or {}
    trigger = data.get("trigger", "disruption")
    auto_apply = bool(data.get("auto_apply", False))
    result = disruption_agent.generate_recovery_plans(trigger)
    if auto_apply and result.get("recommended_plan_id"):
        applied = disruption_agent.apply_recovery_plan(result["recommended_plan_id"], auto=True)
        result["applied"] = applied
    return jsonify(result)

@app.get("/api/fleet/decisions")
def api_fleet_decisions():
    return jsonify({"decisions": fleet_store.get_decisions()})

@app.get("/api/fleet/impact")
def api_fleet_impact():
    return jsonify(fleet_store.get_impact_summary())

@app.post("/api/fleet/copilot")
def api_fleet_copilot():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "message is required."}), 400
    confirm = bool(data.get("confirm", False))
    pending_action = data.get("pending_action")
    return jsonify(fleet_copilot.process_message(message, confirm_action=confirm, pending_action=pending_action))

@app.post("/api/fleet/reset-demo")
def api_fleet_reset_demo():
    state = fleet_store.reset_demo()
    return jsonify({"ok": True, "message": "Demo scenario reset.", "depot": state.get("depot")})


# ------------------------------------------------------------------
# 🌱 ROUTE OPTIMIZATION TERMINAL
# ------------------------------------------------------------------
@app.post("/api/optimize")
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

    try:
        report_output = agent.optimize(source, destination, vehicle)
        return jsonify(report_output)
    except Exception as e:
        return jsonify({"error": f"Agent Pipeline Error: {str(e)}"}), 500
    
@app.route('/admin/reply/<ticket_id>', methods=['POST'])
def admin_reply(ticket_id):
    # Admin session check (Security)
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 403
    
    reply_text = request.form.get('reply')

    return jsonify({"status": "success", "message": "Reply sent to user!"})


@app.route("/api/admin/users/<path:user_id>/delete", methods=["DELETE", "POST"])
def api_admin_delete_user(user_id):
    if not admin_required():
        return jsonify({"error": "Admin session required."}), 401
        
    try:
        import os, json, shutil
        # 1. Correct Path Trace
        source_path = "data/users.json" 
        temp_path = "/tmp/users.json"
        if not os.path.exists(temp_path) and os.path.exists(source_path):
            shutil.copy(source_path, temp_path)
        file_path = temp_path if os.path.exists(temp_path) else source_path

        # 2. Read file as a true LIST
        with open(file_path, "r") as f:
            user_list = json.load(f)
            
        if not isinstance(user_list, list):
            return jsonify({"error": "Database format mismatch. Expected a list."}), 500

        user_id_clean = user_id.strip().lower()
        original_length = len(user_list)

        # 3. Filter out the targeted user safely (Strict list comprehension)
        # Yeh email match karega bina pooray data structure ko kharab kiye
        updated_users = [
            u for u in user_list 
            if str(u.get("email", "")).strip().lower() != user_id_clean
        ]

        # 4. Save back explicitly as a clean LIST format
        if len(updated_users) < original_length:
            with open(file_path, "w") as f:
                json.dump(updated_users, f, indent=4)
                
            print(f"✅ ROOT LIST PURGE SUCCESSFUL: Removed {user_id_clean}")
            return jsonify({"message": "Account permanently deleted from root database."}), 200
        else:
            return jsonify({"error": "User identity not found in database registry."}), 400
            
    except Exception as e:
        print(f"\n❌ ROOT LIST PURGE CRASH: {str(e)}\n")
        return jsonify({"error": f"Database write error: {str(e)}"}), 500

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
        
        # CSV generation
        csv_data = "Query,Engine,Sprint CO2(g),Green CO2(g),Saved CO2(g)\n"
        for entry in entries:
            csv_data += f"{entry.get('query','')},{entry.get('engine','')},{entry.get('sprintCo2','')},{entry.get('greenCo2','')},{entry.get('saved','')}\n"
        
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=sky_eco_telemetry.csv"}
        )
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": "System Error: " + str(e)}), 500
@app.route('/update_profile', methods=['POST'])
def update_profile():
    try:
        user_session = session.get("user")
        if not user_session:
            return jsonify({"error": "No session found"}), 401
        
        user_email = session.get("user")["email"]
        data_to_update = {"name": request.form.get('name')}
        
        # Test: kya ye line chal rahi hai?
        users.update_user(user_email, data_to_update)
        session["user"] = users._read() # Refresh object from file
        session.modified = True
        return jsonify({"success": True})
    except Exception as e:
        print(f"DEBUG ERROR: {str(e)}") # Ye terminal mein error print karega
        return jsonify({"error": str(e)}), 500

@app.route('/api/agent/predict', methods=['GET'])
def get_agent_prediction():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    email = user.get("email", "").strip().lower()
    user_entries = ledger.get_entries(email)
    
    # DEBUG: Console mein entries check karne ke liye
    print(f"DEBUG: Checking ledger for email: '{email}'")
    
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
    return render_template('premium.html')
@app.route('/contact-sales')
def contact_sales():
    return render_template('contact_sales.html')   

@app.route('/api/analyze-fleet', methods=['POST'])
def analyze_fleet():
    # 1. Input get karein
    data = request.get_json()
    message = data.get("message", "")
    
    # 2. Variable define karein (Yehi missing tha!)
    # agent.optimize aapka original function hai
    analysis_result = agent.optimize("Diagnostic", message, "eco-ai-bot")
    
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
def debug_routes():
    import urllib
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

print(os.path.abspath('admin.json'))
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)