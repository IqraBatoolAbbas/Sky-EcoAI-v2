// static/js/premium.js
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("checkoutForm");
  if (!form) return;

  const cardInput = document.getElementById("cardNumber");
  const expiryInput = document.getElementById("expiry");
  const errorBanner = document.getElementById("checkoutError");
  const submitBtn = document.getElementById("checkoutSubmit");

  cardInput.addEventListener("input", () => {
    const digits = cardInput.value.replace(/\D/g, "").slice(0, 19);
    cardInput.value = digits.replace(/(.{4})/g, "$1 ").trim();
  });

  expiryInput.addEventListener("input", () => {
    let digits = expiryInput.value.replace(/\D/g, "").slice(0, 4);
    if (digits.length > 2) digits = `${digits.slice(0, 2)}/${digits.slice(2)}`;
    expiryInput.value = digits;
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name_on_card = document.getElementById("nameOnCard").value.trim();
    const card_number = cardInput.value.replace(/\s+/g, "");
    const expiry = expiryInput.value.trim();
    const cvv = document.getElementById("cvv").value.trim();

    // 🚀 NEW ADDITION (No Deletion): Extract tier value from current URL query parameters
    const urlParams = new URLSearchParams(window.location.search);
    const plan_type = urlParams.get('tier') || 'premium'; 

    // Resetting visibility filters safely without deleting your classes
    if (errorBanner) {
      errorBanner.classList.remove("show");
      errorBanner.style.display = "none";
    }
    
    submitBtn.disabled = true;
    submitBtn.textContent = "Processing payment…";

    try {
      const res = await fetch("/api/premium/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // 🚀 MODIFIED PAYLOAD: Passed plan_type along with existing parameters
        body: JSON.stringify({ name_on_card, card_number, expiry, cvv, plan_type }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Payment failed.");

      // Dynamic custom toast trigger linked with your response keys safely
      if (window.SkyToast) {
        window.SkyToast.show(data.message || "Payment complete — welcome to Premium 👑", "success");
      } else {
        alert("Payment complete — welcome to Premium 👑");
      }
      
      // Kept your structural delay logic perfectly intact
      setTimeout(() => window.location.reload(), 700);
    } catch (err) {
      errorBanner.textContent = err.message;
      errorBanner.classList.add("show");
      
      // Inline rendering patch to make sure CSS visibility rules don't hide the text
      errorBanner.style.display = "block";
      errorBanner.style.color = "var(--danger, #ef4b5f)";
      
      // 🚀 NEW ADDITION: Safely updates fallback text if user selected Pro
      submitBtn.disabled = false;
      submitBtn.textContent = plan_type === 'pro' ? "Pay $49 & upgrade" : "Pay $9 & upgrade";
    }
  });
});