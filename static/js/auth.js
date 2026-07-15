// static/js/auth.js
document.addEventListener("DOMContentLoaded", () => {
  console.log("[Sky Auth Engine]: System successfully initialized.");

  /* ---------------- 1. UNIFIED & CRASH-PROOF PASSWORD TOGGLE ENGINE ---------------- */
  // Global event delegation for all dynamic or static eye icons
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-toggle-for]");
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      const input = document.getElementById(btn.getAttribute("data-toggle-for"));
      if (input) {
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        btn.textContent = showing ? "👁" : "🙈";
      }
    }
  });

  /* ---------------- 2. GLOBAL LOGOUT BUTTON ENGINE ---------------- */
  document.addEventListener("click", async (e) => {
    const logoutTarget = e.target.closest('#userLogoutBtn, .logout-btn, .sky-logout-btn, [href="/logout"]');
    if (logoutTarget) {
      e.preventDefault();
      e.stopPropagation();
      console.log("[Sky Auth]: Logout command intercepted.");

      try {
        // Pehle direct endpoint check karega
        let res = await fetch("/api/logout", { 
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });

        // Agar 404 aaye toh alternate URL use karega
        if (res.status === 404) {
          res = await fetch("/api/auth/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
          });
        }

        if (res.ok) {
          console.log("[Sky Auth]: Session cleared cleanly.");
          window.location.href = "/";
        } else {
          // Fallback forced client redirect agar server response down ho
          window.location.href = "/";
        }
      } catch (err) {
        console.error("Forcing clean exit matrix on failure:", err);
        window.location.href = "/";
      }
    }
  });

  const nextParam = new URLSearchParams(window.location.search).get("next") || "/workspace";

  /* ---------------- 3. LOGIN & REMEMBER ME TRACKER ---------------- */
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    const rememberMeCheck = document.getElementById("rememberMe");
    const emailInput = document.getElementById("loginEmail");
    const savedEmail = localStorage.getItem("sky_remembered_email");
    
    if (savedEmail && emailInput && rememberMeCheck) {
      emailInput.value = savedEmail;
      rememberMeCheck.checked = true;
    }

    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      
      const emailEl = document.getElementById("loginEmail");
      const passwordEl = document.getElementById("loginPassword");
      const errorBanner = document.getElementById("loginError");
      const submitBtn = document.getElementById("loginSubmit");

      if (!emailEl || !passwordEl || !errorBanner || !submitBtn) return;

      // Inline functional style guard injection for login errors
      const showLoginError = (msg, isHTML = false) => {
        if (isHTML) {
          errorBanner.innerHTML = msg;
        } else {
          errorBanner.textContent = msg;
        }
        errorBanner.style.display = "block";
        errorBanner.style.background = "rgba(239, 75, 95, 0.15)";
        errorBanner.style.color = "rgba(239, 75, 95, 1)";
        errorBanner.style.padding = "12px";
        errorBanner.style.borderRadius = "6px";
        errorBanner.style.marginBottom = "15px";
        errorBanner.style.border = "1px solid rgba(239, 75, 95, 0.3)";
      };

      const email = emailEl.value.trim();
      const password = passwordEl.value;

      if (!email.includes("@") || password.length < 1) {
        showLoginError("Enter both your email and password.");
        return;
      }

      if (rememberMeCheck && rememberMeCheck.checked) {
        localStorage.setItem("sky_remembered_email", email);
      } else {
        localStorage.removeItem("sky_remembered_email");
      }

      errorBanner.style.display = "none";
      submitBtn.disabled = true;
      submitBtn.textContent = "Logging in…";

      try {
        const res = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await res.json();

        if (!res.ok) {
          if (data.error && data.error.toLowerCase().includes("no account")) {
            showLoginError(`${data.error} <a href="/signup" style="color:var(--horizon); font-weight:700;">Create one →</a>`, true);
          } else {
            showLoginError(data.error || "Login failed.");
          }
          submitBtn.disabled = false;
          submitBtn.textContent = "Log in";
          return;
        }

        if (typeof SkyToast !== 'undefined') {
          SkyToast.show(`Welcome back, ${data.name.split(" ")[0]}.`, "success");
        }
        setTimeout(() => (window.location.href = nextParam), 450);
      } catch (err) {
        showLoginError("Couldn't reach the server. Please try again.");
        submitBtn.disabled = false;
        submitBtn.textContent = "Log in";
      }
    });
  }

  /* ---------------- 4. SIGNUP & REAL-TIME STRENGTH METRIC ---------------- */
  const signupForm = document.getElementById("signupForm");
  if (signupForm) {
    const pwInput = document.getElementById("signupPassword");
    const strengthBar = document.getElementById("strengthBar");
    const strengthLabel = document.getElementById("strengthLabel");

    if (pwInput && strengthBar && strengthLabel) {
      pwInput.addEventListener("input", () => {
        const val = pwInput.value;
        let score = 0;
        
        if (val.length >= 8) score += 25;
        if (/[0-9]/.test(val)) score += 25;
        if (/[A-Z]/.test(val)) score += 25;
        if (/[!@#$%^&*()\-=_+]/.test(val)) score += 25;
        
        strengthBar.style.width = `${score}%`;
        
        if (val.length === 0) {
          strengthBar.style.width = "0%";
          strengthLabel.textContent = "Use 8+ characters with uppercase, numbers, and symbols.";
          strengthLabel.style.color = "var(--text-faint)";
        } else if (score < 50) {
          strengthBar.style.background = "rgba(239, 75, 95, 0.8)"; 
          strengthLabel.textContent = "Weak — Add numbers, capital letters, or special symbols.";
          strengthLabel.style.color = "rgba(239, 75, 95, 1)";
        } else if (score < 100) {
          strengthBar.style.background = "var(--horizon)"; 
          strengthLabel.textContent = "Getting stronger — Add missing components for full security.";
          strengthLabel.style.color = "var(--horizon)";
        } else {
          strengthBar.style.background = "var(--altitude)"; 
          strengthLabel.textContent = "Strong cryptographic security matrix achieved! ✨";
          strengthLabel.style.color = "var(--altitude)";
        }
      });
    }

    signupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      
      const nameEl = document.getElementById("signupName");
      const emailEl = document.getElementById("signupEmail");
      const passwordEl = document.getElementById("signupPassword");
      const agreeEl = document.getElementById("agreeTerms");
      const errorBanner = document.getElementById("signupError");
      const submitBtn = document.getElementById("signupSubmit");

      if (!nameEl || !emailEl || !passwordEl || !errorBanner || !submitBtn) return;

      const name = nameEl.value.trim();
      const email = emailEl.value.trim();
      const password = passwordEl.value;
      const agree = agreeEl ? agreeEl.checked : false;

      // Inline functional style guard injection for signup errors
      const showSignupError = (msg, isHTML = false) => {
        if (isHTML) {
          errorBanner.innerHTML = msg;
        } else {
          errorBanner.textContent = msg;
        }
        errorBanner.style.display = "block";
        errorBanner.style.background = "rgba(239, 75, 95, 0.15)";
        errorBanner.style.color = "rgba(239, 75, 95, 1)";
        errorBanner.style.padding = "12px";
        errorBanner.style.borderRadius = "6px";
        errorBanner.style.marginBottom = "15px";
        errorBanner.style.border = "1px solid rgba(239, 75, 95, 0.3)";
      };

      if (!name || name.length < 2) {
        showSignupError("Please enter your full name (at least 2 characters).");
        return;
      }
      if (!email.includes("@")) {
        showSignupError("Please enter a valid email address.");
        return;
      }
      if (password.length < 8) {
        showSignupError("Password must be at least 8 characters long.");
        return;
      }
      if (!/[0-9]/.test(password)) {
        showSignupError("Password must include at least one numerical digit (0-9).");
        return;
      }
      if (!/[A-Z]/.test(password)) {
        showSignupError("Password must include at least one uppercase letter (A-Z).");
        return;
      }
      if (!/[!@#$%^&*()\-=_+]/.test(password)) {
        showSignupError("Password must include at least one special character (e.g., !, @, #, $, %).");
        return;
      }
      if (!agree) {
        showSignupError("Please agree to the Terms of Service to continue.");
        return;
      }

      errorBanner.style.display = "none";
      submitBtn.disabled = true;
      submitBtn.textContent = "Creating account…";

      try {
        const res = await fetch("/api/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, email, password }),
        });
        const data = await res.json();

        if (!res.ok) {
          if (data.error && data.error.toLowerCase().includes("already exists")) {
            showSignupError(`${data.error} <a href="/login" style="color:var(--horizon); font-weight:700;">Log in →</a>`, true);
          } else {
            showSignupError(data.error || "Could not create account.");
          }
          submitBtn.disabled = false;
          submitBtn.textContent = "Create account";
          return;
        }

        if (typeof SkyToast !== 'undefined') {
          SkyToast.show(`Account created — welcome, ${data.name.split(" ")[0]}.`, "success");
        }
        setTimeout(() => (window.location.href = "/workspace"), 450);
      } catch (err) {
        showSignupError("Couldn't reach the server. Please try again.");
        submitBtn.disabled = false;
        submitBtn.textContent = "Create account";
      }
    });
  }
});