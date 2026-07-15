/**
 * Free browser speech recognition (Web Speech API).
 * No Whisper install / no API key. Chrome/Edge best support.
 * Optional path later: local Whisper via /api/voice/transcribe.
 */
window.SkyVoice = (function () {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  function supported() {
    return Boolean(SR);
  }

  function listen({ onPartial, onFinal, onError, lang = "en-US" } = {}) {
    if (!SR) {
      onError?.("Voice not supported in this browser. Use Chrome or Edge.");
      return { stop() {} };
    }
    const rec = new SR();
    rec.lang = lang;
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;

    rec.onresult = (e) => {
      let interim = "";
      let finalText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t;
        else interim += t;
      }
      if (interim) onPartial?.(interim);
      if (finalText) onFinal?.(finalText.trim());
    };
    rec.onerror = (ev) => onError?.(ev.error || "speech error");
    rec.start();
    return {
      stop() {
        try {
          rec.stop();
        } catch (_) {}
      },
    };
  }

  function attachMicButton(button, inputEl, { onSubmit } = {}) {
    if (!button || !inputEl) return;
    if (!supported()) {
      button.title = "Voice requires Chrome/Edge";
      button.disabled = true;
      button.style.opacity = "0.45";
      return;
    }

    let active = null;
    button.addEventListener("click", () => {
      if (active) {
        active.stop();
        active = null;
        button.classList.remove("listening");
        button.setAttribute("aria-pressed", "false");
        return;
      }
      button.classList.add("listening");
      button.setAttribute("aria-pressed", "true");
      active = listen({
        onPartial: (t) => {
          inputEl.value = t;
        },
        onFinal: (t) => {
          inputEl.value = t;
          button.classList.remove("listening");
          button.setAttribute("aria-pressed", "false");
          active = null;
          if (onSubmit) onSubmit(t);
        },
        onError: (err) => {
          button.classList.remove("listening");
          button.setAttribute("aria-pressed", "false");
          active = null;
          if (window.SkyToast) SkyToast.show("Mic: " + err, "default");
        },
      });
    });
  }

  return { supported, listen, attachMicButton };
})();
