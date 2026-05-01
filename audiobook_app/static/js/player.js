(function () {
  const playerPanel = document.getElementById("playerPanel");
  const audio = document.getElementById("audioPlayer");
  const playPauseButton = document.getElementById("playPauseButton");
  const stopButton = document.getElementById("stopButton");
  const seekBar = document.getElementById("seekBar");
  const timeDisplay = document.getElementById("timeDisplay");
  const downloadButton = document.getElementById("downloadButton");

  function formatTime(seconds) {
    if (!Number.isFinite(seconds)) {
      return "0:00";
    }

    const totalSeconds = Math.max(0, Math.floor(seconds));
    const minutes = Math.floor(totalSeconds / 60);
    const remainingSeconds = totalSeconds % 60;
    return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
  }

  function updateTime() {
    seekBar.value = audio.duration ? String((audio.currentTime / audio.duration) * 1000) : "0";
    timeDisplay.textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
  }

  function resetPlayer() {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    playPauseButton.textContent = "Play";
    seekBar.value = "0";
    timeDisplay.textContent = "0:00 / 0:00";
    downloadButton.removeAttribute("href");
    playerPanel.classList.remove("is-visible");
    playerPanel.hidden = true;
  }

  function showAudio(detail, isComplete) {
    const sourceUrl = `${detail.preview_url}?v=${Date.now()}`;
    if (!audio.src || isComplete) {
      audio.src = sourceUrl;
      audio.load();
    }

    downloadButton.href = detail.download_url;
    downloadButton.download = "audiobook.mp3";
    playerPanel.hidden = false;
    requestAnimationFrame(() => playerPanel.classList.add("is-visible"));
  }

  playPauseButton.addEventListener("click", async () => {
    if (!audio.src) {
      return;
    }

    if (audio.paused) {
      await audio.play();
      playPauseButton.textContent = "Pause";
      return;
    }

    audio.pause();
    playPauseButton.textContent = "Play";
  });

  stopButton.addEventListener("click", () => {
    audio.pause();
    audio.currentTime = 0;
    playPauseButton.textContent = "Play";
    updateTime();
  });

  seekBar.addEventListener("input", () => {
    if (!audio.duration) {
      return;
    }
    audio.currentTime = (Number(seekBar.value) / 1000) * audio.duration;
  });

  audio.addEventListener("loadedmetadata", updateTime);
  audio.addEventListener("timeupdate", updateTime);
  audio.addEventListener("ended", () => {
    playPauseButton.textContent = "Play";
  });

  window.addEventListener("audiobook:preview-ready", (event) => {
    showAudio(event.detail, false);
  });

  window.addEventListener("audiobook:ready", (event) => {
    showAudio(event.detail, true);
  });

  window.addEventListener("audiobook:reset-player", resetPlayer);
})();
