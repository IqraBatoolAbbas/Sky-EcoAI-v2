// static/js/tickets.js
document.addEventListener("DOMContentLoaded", async () => {
  const list = document.getElementById("ticketsList");

  const timeAgo = (unixSeconds) => {
    const diff = Math.floor(Date.now() / 1000) - unixSeconds;
    if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
    return `${Math.floor(diff / 86400)} day(s) ago`;
  };

  try {
    const res = await fetch("/api/my-tickets");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Couldn't load tickets.");

    if (!data.tickets.length) {
      list.innerHTML = `<div class="glass-card empty-state"><span class="icon">🎫</span>No tickets yet — submit one from the <a href="/about#contact" style="color:var(--horizon);">support center</a>.</div>`;
      return;
    }

    /* ---------------- 🟢 FALLBACK PROTECTION APPLIED INSIDE MAP LOOP ---------------- */
    list.innerHTML = data.tickets.map((t) => {
      // Backend attributes flexibility safeguard: Check all possible naming variants
      const ticketResponse = t.response || t.admin_response || t.reply || null;
      const responseTime = t.responded_at || t.updated_at || t.created_at;
      const isAnswered = t.status === 'answered' || t.status === 'resolved' || !!ticketResponse;

      return `
        <div class="glass-card" style="padding:24px;">
          <div style="display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap;">
            <span class="mono" style="font-weight:700; color:var(--horizon);">${t.ticket_id}</span>
            <span class="engine-badge ${isAnswered ? 'electric' : 'petrol'}">${(t.status || 'pending').toUpperCase()}</span>
          </div>
          <div style="font-size:12.5px; color:var(--text-faint); margin:8px 0 14px;">${t.category} · dispatched ${timeAgo(t.created_at)}</div>
          <p style="color:var(--text-main); margin-bottom:${ticketResponse ? '14px' : '0'};word-wrap: break-word; overflow-wrap: break-word; white-space: pre-wrap;">${t.message}</p>
          ${ticketResponse ? `
            <div style="background:var(--glass-bg-strong); border-left:3px solid var(--stratos); border-radius:8px; padding:12px 16px;">
              <div style="font-size:12px; font-weight:700; color:var(--stratos); margin-bottom:6px;">ADMIN RESPONSE · ${timeAgo(responseTime)}</div>
              <p style="margin:0; color:var(--text-main);word-wrap: break-word; overflow-wrap: break-word; white-space: pre-wrap;">${ticketResponse}</p>
            </div>` : `<div style="font-size:12.5px; color:var(--text-faint); margin-top:10px;">Awaiting a response from the support desk.</div>`}
        </div>
      `;
    }).join("");
  } catch (err) {
    list.innerHTML = `<div class="glass-card empty-state"><span class="icon">⚠️</span>${err.message}</div>`;
  }
});