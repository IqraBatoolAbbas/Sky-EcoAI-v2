// static/js/admin.js

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-toggle-for]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.getAttribute("data-toggle-for"));
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.textContent = showing ? "👁" : "🙈";
    });
  });

  /* ---------------- ADMIN LOGIN ---------------- */
  const loginForm = document.getElementById("adminLoginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("adminEmail").value.trim();
      const password = document.getElementById("adminPassword").value;
      const errorBanner = document.getElementById("adminLoginError");
      const submitBtn = document.getElementById("adminLoginSubmit");

      errorBanner.classList.remove("show");
      submitBtn.disabled = true;
      submitBtn.textContent = "Verifying…";

      try {
        const res = await fetch("/api/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Login failed.");
        window.location.href = "/admin";
      } catch (err) {
        errorBanner.textContent = err.message;
        errorBanner.classList.add("show");
        submitBtn.disabled = false;
        submitBtn.textContent = "Enter console";
      }
    });
  }

  /* ---------------- ADMIN DASHBOARD ---------------- */
  const ticketQueue = document.getElementById("ticketQueue");
  const userList = document.getElementById("userList");
  if (!ticketQueue || !userList) return;

  const timeAgo = (unixSeconds) => {
    const diff = Math.floor(Date.now() / 1000) - unixSeconds;
    if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
    return `${Math.floor(diff / 86400)} day(s) ago`;
  };

  // ⚡ SAFETY LOCK: Re-indexing loop ko rokne ke liye template flag
  // ⚡ OPTIMIZED ADMIN LIFECYCLE: Standard boolean flag to control dynamic toast rendering
  let isOverviewLoading = false;

  async function loadOverview(showToast = false) {
    if (isOverviewLoading) return;
    isOverviewLoading = true;

    try {
      const res = await fetch("/api/admin/overview");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Couldn't load admin data.");

      document.getElementById("statUsers").textContent = data.stats.total_users;
      document.getElementById("statPremium").textContent = data.stats.premium_users;
      document.getElementById("statOpen").textContent = data.stats.open_tickets;
      document.getElementById("statTotal").textContent = data.stats.total_tickets;

      renderTickets(data.tickets);
      renderUsers(data.users);

      // 🎯 Notification sirf tabhi chalegi jab explicitly hum data updates/actions par true bhejenge
      if (showToast) {
        if (typeof SkyToast !== "undefined") {
          SkyToast.show("Dashboard data re-indexed!", "success");
        } else {
          console.log("Dashboard data re-indexed!");
        }
      }
    } catch (err) {
      if (ticketQueue) {
        ticketQueue.innerHTML = `<p style="color:var(--danger);">${err.message}</p>`;
      }
    } finally {
      isOverviewLoading = false; // Lock open for next sequence pipeline iterations
    }
  }

  function renderTickets(tickets) {
    if (!tickets.length) {
      ticketQueue.innerHTML = `<p style="color:var(--text-faint);">No tickets have been submitted yet.</p>`;
      return;
    }

    ticketQueue.innerHTML = tickets.map((t) => {
      const status = t.status || "open";
      const hasAdminReplied = t.response && !t.response.includes("🤖 [AI Assistant]");

      return `
        <div class="glass-card" style="padding:20px; border-left: 4px solid ${status === 'answered' ? '#00e6b4' : '#ffaa00'}; margin-bottom:15px;">
          <div style="display:flex; justify-content:space-between; align-items:center; mb:10px;">
            <span class="mono" style="font-weight:700; color:var(--horizon);">${t.ticket_id}</span>
            <span class="engine-badge" style="
              padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;
              background: ${status === 'answered' ? 'rgba(0, 230, 180, 0.12)' : 'rgba(255, 170, 0, 0.12)'};
              color: ${status === 'answered' ? '#00e6b4' : '#ffaa00'};
            ">${status.toUpperCase()}</span>
          </div>
          <div style="font-size:12px; color:var(--text-faint); margin:4px 0 10px;">
            User: <strong>${t.email}</strong> · Type: ${t.category} · ${timeAgo(t.created_at)}
          </div>
          <p style="color:var(--text-main); margin: 0 0 14px 0; font-size:13.5px; line-height:1.4;">${t.message}</p>
          
          ${t.response ? `
            <div style="background:rgba(255,255,255,0.02); padding:10px 14px; border-radius:6px; font-size:13px; margin-bottom:10px;">
              <span style="color:#00e6b4; font-weight:700; font-size:11px;">✔ CURRENT LOGGED RESPONSE:</span>
              <p style="margin:4px 0 0 0; color:var(--text-muted); white-space: pre-wrap;">${t.response}</p>
            </div>
          ` : ''}

          ${!hasAdminReplied ? `
            <div style="display:flex; gap:8px; margin-top:10px;">
              <input type="text" data-ticket="${t.ticket_id}" placeholder="Type human admin solution here... (Will overwrite or append)" 
                style="flex:1; padding:8px 12px; background:var(--glass-bg-strong); border:1px solid var(--horizon); border-radius:6px; color:var(--text-main); font-size:13px;">
              <button class="respond-btn primary-btn" data-ticket="${t.ticket_id}" style="padding:8px 16px; font-size:13px;">Send</button>
            </div>
          ` : `
            <div style="color: #00e6b4; font-size: 12px; font-weight: bold; margin-top: 5px;">
              📢 Human Admin has finalized this thread.
            </div>
          `}
        </div>
      `;
    }).join("");

    ticketQueue.querySelectorAll(".respond-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const ticketId = btn.getAttribute("data-ticket");
        const input = ticketQueue.querySelector(`input[data-ticket="${ticketId}"]`);
        const response = input.value.trim();
        
        if (response.length < 3) {
          if (typeof SkyToast !== "undefined") {
            // SkyToast.show("Write at least a few words before sending.", "error");
          } else {
            alert("Write at least a few words before sending.");
          }
          return;
        }

        btn.disabled = true;
        btn.textContent = "Sending…";
        
        try {
          const res = await fetch(`/api/admin/tickets/${ticketId}/respond`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ response }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || "Couldn't send response.");
          
          if (typeof SkyToast !== "undefined") {
            SkyToast.show("Response updated by Admin.", "success");
          }
          loadOverview(false); // Action-based trigger
        } catch (err) {
          if (typeof SkyToast !== "undefined") {
            SkyToast.show(err.message, "error");
          } else {
            alert(err.message);
          }
          btn.disabled = false;
          btn.textContent = "Send";
        }
      });
    });
  }

  /* ---------------- 🔥 RENDER USERS METRICS WITH DELETE ACTION ---------------- */
  function renderUsers(users) {
    if (!users.length) {
      userList.innerHTML = `<p style="color:var(--text-faint);">No registered users yet.</p>`;
      return;
    }
    userList.innerHTML = users.map((u) => {
      const userPlan = u.plan || (u.preferences && u.preferences.plan) || "free";
      const userIdentifier = u.id || u.email;

      return `
        <div class="trip-history-item" style="display:flex; justify-content:space-between; align-items:center; padding:10px; background:rgba(255,255,255,0.01); border-radius:6px; margin-bottom:6px;">
          <span>${u.name} ${userPlan === "premium" ? "👑" : ""}<br><span class="muted" style="font-size:12px; color:var(--text-faint);">${u.email}</span></span>
          <div style="display:flex; align-items:center; gap:10px;">
            <span class="engine-badge" style="
              padding:2px 6px; border-radius:4px; font-size:10px; font-weight:700;
              background:${userPlan === 'premium' ? 'rgba(0, 230, 180, 0.12)' : 'rgba(255,255,255,0.05)'};
              color:${userPlan === 'premium' ? '#00e6b4' : 'var(--text-muted)'};
            ">${userPlan.toUpperCase()}</span>
            
            <button class="delete-user-btn" data-id="${userIdentifier}" style="
              background: rgba(239, 75, 95, 0.1); color: #ef4b5f; border: 1px solid rgba(239, 75, 95, 0.2);
              padding: 3px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; font-family: inherit;
              transition: all 0.2s ease;
            " onmouseover="this.style.background='rgba(239, 75, 95, 0.2)'" onmouseout="this.style.background='rgba(239, 75, 95, 0.1)'">
              🗑️ Delete
            </button>
          </div>
        </div>
      `;
    }).join("");
  }

  /* ---------------- 🎯 GLOBAL INTERCEPTING CLICK EVENT LISTENER FOR DELETE ---------------- */
  let isDeleting = false; // Extra safety guard for click event double-firing

  document.addEventListener("click", async (e) => {
    if (e.target.classList.contains("delete-user-btn")) {
      if (isDeleting) return;
      
      const userId = e.target.getAttribute("data-id");
      
      if (confirm(`Are you absolutely sure you want to permanently delete account: ${userId}?`)) {
        isDeleting = true;
        try {
          const response = await fetch(`/api/admin/users/${encodeURIComponent(userId)}/delete`, {
            method: "POST", 
            headers: { "Content-Type": "application/json" }
          });
          
          const result = await response.json();
          if (response.ok) {
            // Smooth soft-reload after layout purging layout items
            loadOverview(true);
            
            // 🚀 AUTOMATIC VISUAL COMPLIANCE: Hard refresh template framework 
            setTimeout(() => {
              window.location.reload();
            }, 600);
          } else {
            alert(result.error || "Failed to delete user.");
            isDeleting = false;
          }
        } catch (err) {
          console.error("Delete execution tracking pipeline crash context:", err);
          isDeleting = false;
        }
      }
    }
  });

  loadOverview(false); // Initial load (Silent execution, no initial alert tracking)
});