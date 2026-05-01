(function () {
  const convertButton = document.getElementById("convertButton");
  const convertButtonText = document.getElementById("convertButtonText");
  const convertStatus = document.getElementById("convertStatus");
  const textPreview = document.getElementById("textPreview");
  const voiceSelect = document.getElementById("voiceSelect");
  const speedRange = document.getElementById("speedRange");
  const speedLabel = document.getElementById("speedLabel");
  const speedValue = document.getElementById("speedValue");

  function rateLabel(value) {
    if (value < 0) {
      return "Slower";
    }
    if (value > 0) {
      return "Faster";
    }
    return "Normal";
  }

  function rateString(value) {
    const numericValue = Number(value) || 0;
    return `${numericValue > 0 ? "+" : ""}${numericValue}%`;
  }

  function setConvertStatus(message, type) {
    convertStatus.textContent = message;
    convertStatus.classList.toggle("is-error", type === "error");
    convertStatus.classList.toggle("is-success", type === "success");
  }

  function setLoading(isLoading) {
    convertButton.disabled = isLoading || !textPreview.value.trim() || !voiceSelect.value;
    convertButton.classList.toggle("is-loading", isLoading);
    convertButtonText.textContent = isLoading ? "Generating audiobook..." : "Convert to MP3";
  }

  function refreshButtonState() {
    convertButton.disabled = !textPreview.value.trim() || !voiceSelect.value || voiceSelect.disabled;
  }

  function updateSpeedDisplay() {
    const value = Number(speedRange.value);
    speedLabel.textContent = rateLabel(value);
    speedValue.textContent = rateString(value);
  }

  async function convertText() {
    if (!textPreview.value.trim()) {
      setConvertStatus("Upload a readable PDF first.", "error");
      return;
    }

    setLoading(true);
    setConvertStatus("Connecting to edge-tts and generating MP3...", "");

    try {
      const response = await fetch("/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: textPreview.value,
          voice: voiceSelect.value,
          speed: rateString(speedRange.value),
        }),
      });
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || "Conversion failed.");
      }

      setConvertStatus("MP3 generated.", "success");
      window.dispatchEvent(new CustomEvent("audiobook:ready", { detail: payload.data }));
    } catch (error) {
      setConvertStatus(error.message || "Conversion failed.", "error");
    } finally {
      setLoading(false);
    }
  }

  speedRange.addEventListener("input", updateSpeedDisplay);
  voiceSelect.addEventListener("change", refreshButtonState);
  convertButton.addEventListener("click", convertText);

  window.addEventListener("audiobook:upload-start", () => {
    setConvertStatus("", "");
    window.dispatchEvent(new CustomEvent("audiobook:reset-player"));
    refreshButtonState();
  });

  window.addEventListener("audiobook:upload-complete", () => {
    refreshButtonState();
  });

  updateSpeedDisplay();
  refreshButtonState();
})();
