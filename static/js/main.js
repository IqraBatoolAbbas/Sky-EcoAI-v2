// static/js/main.js
document.addEventListener("DOMContentLoaded", () => {  
  /* ---------------- EXACT THEME TOGGLE CODE LOCATION ---------------- */
  const htmlTag = document.documentElement;
  const themeToggler = document.getElementById("themeToggler");

  // 1. Initial configuration on page load
  const savedTheme = localStorage.getItem("sky-theme") || "dark";
  htmlTag.setAttribute("data-theme", savedTheme);
  updateTogglerIcon(savedTheme);

  // Click handler trigger matrix
  if (themeToggler) {
    themeToggler.addEventListener("click", () => {
      const currentTheme = htmlTag.getAttribute("data-theme");
      const newTheme = currentTheme === "dark" ? "light" : "dark";
      
      htmlTag.setAttribute("data-theme", newTheme);
      localStorage.setItem("sky-theme", newTheme);
      updateTogglerIcon(newTheme);
    });
  }

  // 3. Isolated UI modifier function
  function updateTogglerIcon(theme) {
    if (!themeToggler) return;
    if (theme === "dark") {
      themeToggler.textContent = "☾";
      themeToggler.style.color = "var(--horizon, #f2a65a)";
    } else {
      themeToggler.textContent = "☀";
      themeToggler.style.color = "#10131c";
    }
  }

  /* ---------------- GLOBAL CUSTOM NOTIFICATION ENGINE ---------------- */
  window.SkyToast = {
    show(message, type = "default") {
      /* ---------------- MODERN GLASS UI THEME RIG ---------------- */
      let toastContainer = document.getElementById("skyToastContainer");
      
      // If the viewport rendering structural anchor does not exist, create it dynamically
      if (!toastContainer) {
        toastContainer = document.createElement("div");
        toastContainer.id = "skyToastContainer";
        toastContainer.style.cssText = `
          position: fixed;
          bottom: 24px;
          right: 24px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          z-index: 9999;
          font-family: var(--font-body), sans-serif;
        `;
        document.body.appendChild(toastContainer);
      }

      const toast = document.createElement("div");
      toast.className = `sky-toast toast-${type}`;
      
      // Glassmorphic styling matching portfolio standards
      let badgeColor = "var(--horizon)";
      if (type === "success") badgeColor = "var(--altitude)";
      if (type === "error") badgeColor = "rgba(239, 75, 95, 1)";

      toast.style.cssText = `
        background: rgba(25, 28, 41, 0.75);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: var(--text-main, #ffffff);
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 250px;
        max-width: 400px;
        font-size: 13px;
        border-left: 4px solid ${badgeColor};
        transform: translateX(120%);
        transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275), opacity 0.3s ease;
        opacity: 0;
      `;

      // Assigning visual telemetry state icons
      const icon = type === "success" ? "✅" : type === "error" ? "⚠" : "ℹ️";
      toast.innerHTML = `<span>${icon}</span><span style="flex-grow:1;">${message}</span>`;
      
      toastContainer.appendChild(toast);

      // Trigger micro-task macro-task animation frames smoothly
      setTimeout(() => {
        toast.style.transform = "translateX(0)";
        toast.style.opacity = "1";
      }, 50);

      // Dynamic cleanup configuration sequence
      setTimeout(() => {
        toast.style.transform = "translateX(120%)";
        toast.style.opacity = "0";
        setTimeout(() => {
          toast.remove();
        }, 300);
      }, 4000);
    }
  };

console.log("main.js load ho gaya!");

const navToggle = document.getElementById("navToggle");
const navMenu = document.getElementById("navLinks");

// IF CHECK: Agar navToggle milta hai, tabhi listener lagao
if (navToggle && navMenu) {
    navToggle.addEventListener("click", () => {
        console.log("Button click hua!");
        navMenu.classList.toggle("open");
    });
} else {
    console.warn("navToggle ya navMenu nahi mila - shayad ye page par nahi hai.");
}

/* ---------------- ACTIVE ROUTE ANCHOR HIGHLIGHTING ---------------- */
const normalizePath = (value) => {
  if (!value) return "/";
  const stripped = value.split("?")[0].split("#")[0];
  if (stripped.length > 1 && stripped.endsWith("/")) return stripped.slice(0, -1);
  return stripped || "/";
};

const currentPath = normalizePath(window.location.pathname);
const navItems = Array.from(document.querySelectorAll(".nav-item[data-path]"));

let bestMatch = null;
for (const item of navItems) {
  const itemPath = normalizePath(item.dataset.path);
  const isHome = itemPath === "/";
  const isExactMatch = currentPath === itemPath;
  const isSectionMatch = !isHome && currentPath.startsWith(`${itemPath}/`);

  if (isExactMatch || isSectionMatch) {
    if (!bestMatch || itemPath.length > bestMatch.path.length) {
      bestMatch = { item, path: itemPath };
    }
  }
}

navItems.forEach((item) => item.classList.remove("active"));
if (bestMatch) {
  bestMatch.item.classList.add("active");
}

  
  /* ---------------- USER DROPDOWN REDIRECTION PROTOCOLS ---------------- */
  const userChipBtn = document.getElementById("userChipBtn");
  const userDropdown = document.getElementById("userDropdown");

  if (userChipBtn && userDropdown) {
    // 1. Profile trigger par click handle karna
    userChipBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation(); // Taake immediate window click close na ho jaye
      userDropdown.classList.toggle("show");
    });

    // 2. Dropdown ke andar items routing permissions bypass rule
    userDropdown.addEventListener("click", (e) => {
      const isRedirectionNode = e.target.closest("a, button");
      if (isRedirectionNode) {
        userDropdown.classList.remove("show"); // Standard closure on switch
      } else {
        e.stopPropagation();
      }
    });

    // 3. Document body click detection for collapsing layout
    document.addEventListener("click", (e) => {
      if (!userChipBtn.contains(e.target) && !userDropdown.contains(e.target)) {
        userDropdown.classList.remove("show");
      }
    });
  }
});