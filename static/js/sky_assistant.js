document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("skyAssistantRoot")) return;

  const root = document.createElement("div");
  root.id = "skyAssistantRoot";
  root.innerHTML = `
    <div class="sky-assistant-panel" id="skyAssistPanel" aria-hidden="true">
      <div class="sky-assistant-head">
        <h3>Sky Assistant</h3>
        <p>RAG-grounded help · demo loop, recovery, carbon estimates</p>
      </div>
      <div class="sky-assistant-chips" id="skyAssistChips">
        <button type="button" data-q="How do I run the demo loop?">Demo loop</button>
        <button type="button" data-q="What are Economy Green and Service modes?">Planning modes</button>
        <button type="button" data-q="What happens on vehicle breakdown?">Breakdown</button>
        <button type="button" data-q="Do I need Gemini or OpenAI?">API keys</button>
      </div>
      <div class="sky-assistant-msgs" id="skyAssistMsgs"></div>
      <form class="sky-assistant-form" id="skyAssistForm">
        <button type="button" class="mic-btn" id="skyAssistMic" title="Voice (Chrome/Edge)" aria-pressed="false">🎤</button>
        <input id="skyAssistInput" placeholder="Ask for help…" autocomplete="off" />
        <button type="submit">Ask</button>
      </form>
    </div>
    <button class="sky-assistant-fab" id="skyAssistFab" type="button" aria-label="Open Sky Assistant">✦</button>
  `;
  document.body.appendChild(root);

  const panel = document.getElementById("skyAssistPanel");
  const fab = document.getElementById("skyAssistFab");
  const msgs = document.getElementById("skyAssistMsgs");
  const form = document.getElementById("skyAssistForm");
  const input = document.getElementById("skyAssistInput");

  const append = (text, role, sources = []) => {
    const el = document.createElement("div");
    el.className = `sky-a-msg ${role}`;
    el.textContent = text;
    if (sources.length) {
      const src = document.createElement("div");
      src.className = "rag-src";
      src.textContent = "Sources: " + sources.map((s) => s.source || s).join(", ");
      el.appendChild(src);
    }
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
  };

  append(
    "Hi — I can explain the Control Tower demo, planning modes, disruptions, and carbon estimates. Answers are grounded in product docs and live fleet state.",
    "bot"
  );

  fab.addEventListener("click", () => {
    const open = panel.classList.toggle("open");
    fab.classList.toggle("open", open);
    fab.textContent = open ? "✕" : "✦";
    panel.setAttribute("aria-hidden", open ? "false" : "true");
    if (open) input.focus();
  });

  document.getElementById("skyAssistChips").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-q]");
    if (!btn) return;
    send(btn.dataset.q);
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    send(q);
  });

  if (window.SkyVoice) {
    SkyVoice.attachMicButton(document.getElementById("skyAssistMic"), input, {
      onSubmit: (t) => {
        input.value = "";
        send(t);
      },
    });
  }

  async function send(q) {
    append(q, "user");
    try {
      const res = await fetch("/api/help/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ message: q }),
      });
      const raw = await res.text();
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        throw new Error(
          res.status === 404
            ? "Help API not found — restart the Flask server (python app.py)."
            : `Server returned non-JSON (HTTP ${res.status}). Restart python app.py.`
        );
      }
      if (!res.ok) throw new Error(data.error || res.statusText);
      append(data.reply || "No answer.", "bot", data.rag?.sources || []);
    } catch (err) {
      append("Sorry — " + err.message, "bot");
    }
  }
});
