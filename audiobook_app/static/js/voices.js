(function () {
  const voiceSelect = document.getElementById("voiceSelect");
  const statusEl = document.getElementById("voiceStatus");

  function addOptionGroup(groupName, voices) {
    if (!voices.length) {
      return;
    }

    const group = document.createElement("optgroup");
    group.label = groupName;

    voices.forEach((voice) => {
      const option = document.createElement("option");
      option.value = voice.short_name;
      option.textContent = `${voice.name} (${voice.short_name})`;
      group.appendChild(option);
    });

    voiceSelect.appendChild(group);
  }

  async function loadVoices() {
    voiceSelect.disabled = true;
    statusEl.textContent = "Loading voices...";

    try {
      const response = await fetch("/voices");
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || "Failed to load voices.");
      }

      voiceSelect.innerHTML = "";
      addOptionGroup("Female", payload.data.voices.Female || []);
      addOptionGroup("Male", payload.data.voices.Male || []);
      addOptionGroup("Neutral", payload.data.voices.Neutral || []);

      if (!voiceSelect.options.length) {
        throw new Error("No English voices were returned.");
      }

      voiceSelect.disabled = false;
      statusEl.textContent = "";
    } catch (error) {
      voiceSelect.innerHTML = "";
      statusEl.textContent = error.message || "Failed to load voices.";
    }
  }

  loadVoices();
})();
