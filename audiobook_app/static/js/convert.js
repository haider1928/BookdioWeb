(function () {
  const convertButton = document.getElementById("convertButton");
  const convertButtonText = document.getElementById("convertButtonText");
  const convertStatus = document.getElementById("convertStatus");
  const retryButton = document.getElementById("retryButton");
  const chunkProgress = document.getElementById("chunkProgress");
  const textPreview = document.getElementById("textPreview");
  const voiceSelect = document.getElementById("voiceSelect");
  const speedRange = document.getElementById("speedRange");
  const speedLabel = document.getElementById("speedLabel");
  const speedValue = document.getElementById("speedValue");

  let activePoll = null;
  let activeJobId = "";
  let previewShown = false;

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
    return `${numericValue >= 0 ? "+" : ""}${numericValue}%`;
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
    convertButton.disabled = !textPreview.value.trim() || !voiceSelect.value || voiceSelect.disabled || Boolean(activeJobId);
  }

  function updateSpeedDisplay() {
    const value = Number(speedRange.value);
    speedLabel.textContent = rateLabel(value);
    speedValue.textContent = rateString(value);
  }

  function updateProgress(status) {
    const done = Number(status.chunks_done || 0);
    const total = Number(status.chunks_total || 0);

    if (total > 0) {
      chunkProgress.hidden = false;
      chunkProgress.max = total;
      chunkProgress.value = done;
      setConvertStatus(`Processing: ${done} of ${total} chunks done`, "");
    }
  }

  function clearPolling() {
    if (activePoll) {
      clearInterval(activePoll);
      activePoll = null;
    }
  }

  function showRetry(message) {
    clearPolling();
    activeJobId = "";
    previewShown = false;
    retryButton.hidden = false;
    setLoading(false);
    setConvertStatus(message, "error");
    refreshButtonState();
  }

  async function pollStatus(jobId) {
    try {
      const response = await fetch(`/status/${jobId}`);
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || "Failed to read conversion status.");
      }

      const status = payload.data;
      updateProgress(status);

      if (status.preview_ready && !previewShown) {
        previewShown = true;
        window.dispatchEvent(new CustomEvent("audiobook:preview-ready", { detail: status }));
      }

      if (status.status === "complete") {
        clearPolling();
        activeJobId = "";
        chunkProgress.value = status.chunks_total || 1;
        setConvertStatus(`Complete: ${status.chunks_done} of ${status.chunks_total} chunks done`, "success");
        window.dispatchEvent(new CustomEvent("audiobook:ready", { detail: status }));
        setLoading(false);
        refreshButtonState();
      }

      if (status.status === "error") {
        showRetry(status.error || "EdgeTTS connection failed. Check internet connection or try again.");
      }
    } catch (error) {
      showRetry(error.message || "Failed to poll conversion status.");
    }
  }

  function startPolling(jobId) {
    clearPolling();
    pollStatus(jobId);
    activePoll = setInterval(() => pollStatus(jobId), 1500);
  }

  async function convertText() {
    if (!textPreview.value.trim()) {
      setConvertStatus("Upload a readable PDF first.", "error");
      return;
    }

    clearPolling();
    activeJobId = "";
    previewShown = false;
    retryButton.hidden = true;
    chunkProgress.hidden = true;
    chunkProgress.value = 0;
    setLoading(true);
    setConvertStatus("Starting conversion job...", "");
    window.dispatchEvent(new CustomEvent("audiobook:reset-player"));

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

      activeJobId = payload.data.job_id;
      updateProgress(payload.data);
      startPolling(activeJobId);
    } catch (error) {
      showRetry(error.message || "Conversion failed.");
    }
  }

  speedRange.addEventListener("input", updateSpeedDisplay);
  voiceSelect.addEventListener("change", refreshButtonState);
  convertButton.addEventListener("click", convertText);
  retryButton.addEventListener("click", convertText);

  window.addEventListener("audiobook:upload-start", () => {
    clearPolling();
    activeJobId = "";
    previewShown = false;
    retryButton.hidden = true;
    chunkProgress.hidden = true;
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
