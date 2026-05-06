document.addEventListener("DOMContentLoaded", () => {
    const convertBtn = document.getElementById("convertBtn");
    const voiceSelect = document.getElementById("voiceSelect");
    const speedRange = document.getElementById("speedRange");
    const speedVal = document.getElementById("speedVal");
    const conversionStatus = document.getElementById("conversionStatus");
    const progressFill = document.getElementById("progressFill");
    const statusText = document.getElementById("statusText");
    const elapsedTime = document.getElementById("elapsedTime");
    const etaTime = document.getElementById("etaTime");
    const voiceInfo = document.getElementById("voiceInfo");
    const playerSection = document.getElementById("playerSection");
    const audioPlayer = document.getElementById("audioPlayer");
    const downloadOptions = document.getElementById("downloadOptions");
    const downloadAudioBtn = document.getElementById("downloadAudioBtn");
    const downloadVideoBtn = document.getElementById("downloadVideoBtn");
    const videoProgress = document.getElementById("videoProgress");
    const videoProgressFill = document.getElementById("videoProgressFill");
    const videoProgressText = document.getElementById("videoProgressText");

    let currentJobId = null;
    let pollInterval = null;
    let videoPollInterval = null;

    speedRange.addEventListener("input", () => {
        const value = parseInt(speedRange.value, 10);
        const sign = value >= 0 ? "+" : "";
        speedVal.textContent = `${sign}${value}%`;
    });

    formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, "0")}`;
    };

    convertBtn.addEventListener("click", async () => {
        if (!window.extractedChunks || window.extractedChunks.length === 0) {
            return;
        }

        const voice = voiceSelect.value;
        const speedValue = parseInt(speedRange.value, 10);
        const speed = `${speedValue >= 0 ? "+" : ""}${speedValue}%`;
        const targetLanguage = window.targetLanguage || 'en';

        convertBtn.disabled = true;
        conversionStatus.classList.remove("hidden");
        statusText.textContent = "Initializing conversion pipeline...";
        progressFill.style.width = "0%";
        downloadOptions.classList.add("hidden");
        hideVideoProgress();
        clearVideoPoll();

        try {
            const response = await fetch("/convert", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text_chunks: window.extractedChunks,
                    voice,
                    speed,
                    target_language: targetLanguage,
                }),
            });
            if (!response.ok) {
                const text = await response.text();
                throw new Error(`Server error ${response.status}: ${text.substring(0, 100)}`);
            }
            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error);
            }

            currentJobId = result.data.job_id;
            voiceInfo.textContent = `Voice: ${voice}`;
            startPolling(currentJobId);
        } catch (error) {
            statusText.textContent = `Error: ${error.message}`;
            convertBtn.disabled = false;
        }
    });

    function startPolling(jobId) {
        if (pollInterval) {
            clearInterval(pollInterval);
        }

        pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${jobId}`);
                if (!response.ok) {
                    const text = await response.text();
                    console.error(`Status poll error ${response.status}: ${text.substring(0, 100)}`);
                    return;
                }
                const result = await response.json();
                if (!result.success) {
                    return;
                }

                const data = result.data;
                const progress = data.chunks_total > 0
                    ? (data.chunks_done / data.chunks_total) * 100
                    : 0;
                progressFill.style.width = `${Math.max(0, Math.min(progress, 100))}%`;

                if (data.status === "processing") {
                    statusText.textContent = `Speech generation: ${data.chunks_done} / ${data.chunks_total} chunks`;
                    elapsedTime.textContent = `Elapsed: ${formatTime(data.elapsed_seconds || 0)}`;
                    etaTime.textContent = data.eta_seconds > 0 ? `ETA: ~${formatTime(data.eta_seconds)}` : `ETA: --`;
                }

                if (data.preview_ready && playerSection.classList.contains("hidden")) {
                    playerSection.classList.remove("hidden");
                    audioPlayer.src = `/preview/${jobId}`;
                    if (window.initKaraoke) {
                        window.initKaraoke(audioPlayer, jobId);
                    }
                }

                if (data.status === "done") {
                    clearInterval(pollInterval);
                    statusText.textContent = data.captions_ready
                        ? "Conversion complete. Captions synchronized."
                        : "Conversion complete. Captions finalizing.";
                    elapsedTime.textContent = `Elapsed: ${formatTime(data.elapsed_seconds || 0)}`;
                    etaTime.textContent = "ETA: done";
                    convertBtn.disabled = false;
                    downloadOptions.classList.remove("hidden");
                    bindDownloadButtons(jobId);
                } else if (data.status === "error") {
                    clearInterval(pollInterval);
                    statusText.textContent = `Error: ${data.error}`;
                    convertBtn.disabled = false;
                }
            } catch (error) {
                console.error("Polling error:", error);
            }
        }, 1000);
    }

    function bindDownloadButtons(jobId) {
        downloadAudioBtn.onclick = () => {
            window.location.href = `/download/${jobId}`;
        };

        downloadVideoBtn.disabled = false;
        downloadVideoBtn.textContent = "Download Video";
        hideVideoProgress();
        downloadVideoBtn.onclick = async () => {
            downloadVideoBtn.disabled = true;
            downloadVideoBtn.textContent = "Generating video...";
            setVideoProgress(0, "Preparing lyric video...");
            await requestVideo(jobId);
        };
    }

    async function requestVideo(jobId) {
        const styleConfig = window.styleSelector ? window.styleSelector.getConfig() : {};
        const targetLanguage = window.targetLanguage || 'en';
        const urduFont = window.urduFont || null;
        try {
            const body = {
                style: styleConfig,
                target_language: targetLanguage,
            };
            if (targetLanguage === 'ur' && urduFont) {
                body.urdu_font = urduFont;
            }
            const response = await fetch(`/download/${jobId}/video`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            if (!response.ok) {
                const text = await response.text();
                throw new Error(`Server error ${response.status}: ${text.substring(0, 100)}`);
            }
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error);
            }

            const progress = Number(result.data.video_progress || 0);
            setVideoProgress(progress, "Processing lyric video...");

            if (result.data.video_status === "done" && result.data.download_url) {
                setVideoProgress(100, "Lyric video ready.");
                window.location.href = result.data.download_url;
                downloadVideoBtn.disabled = false;
                downloadVideoBtn.textContent = "Download Video";
                hideVideoProgressSoon();
                return;
            }

            startVideoPolling(jobId);
        } catch (error) {
            downloadVideoBtn.disabled = false;
            downloadVideoBtn.textContent = "Download Video";
            hideVideoProgress();
            alert(`Video export failed: ${error.message}`);
        }
    }

    function startVideoPolling(jobId) {
        clearVideoPoll();
        videoPollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/download/${jobId}/video/status`);
                if (!response.ok) {
                    const text = await response.text();
                    console.error(`Video status poll error ${response.status}: ${text.substring(0, 100)}`);
                    return;
                }
                const result = await response.json();
                if (!result.success) {
                    return;
                }

                const {
                    video_status: videoStatus,
                    video_error: videoError,
                    video_progress: videoProgressValue,
                    download_url: downloadUrl
                } = result.data;

                const progress = Number(videoProgressValue || 0);
                if (videoStatus === "generating") {
                    setVideoProgress(progress, `Processing lyric video... ${Math.round(progress)}%`);
                }

                if (videoStatus === "done" && downloadUrl) {
                    clearVideoPoll();
                    setVideoProgress(100, "Lyric video ready.");
                    downloadVideoBtn.disabled = false;
                    downloadVideoBtn.textContent = "Download Video";
                    window.location.href = downloadUrl;
                    hideVideoProgressSoon();
                    return;
                }

                if (videoStatus === "error") {
                    clearVideoPoll();
                    downloadVideoBtn.disabled = false;
                    downloadVideoBtn.textContent = "Download Video";
                    hideVideoProgress();
                    alert(`Video export failed: ${videoError || "Unknown error"}`);
                }
            } catch (error) {
                console.error("Video status poll failed", error);
            }
        }, 2000);
    }

    function clearVideoPoll() {
        if (videoPollInterval) {
            clearInterval(videoPollInterval);
            videoPollInterval = null;
        }
    }

    function setVideoProgress(percent, message) {
        videoProgress.classList.remove("hidden");
        videoProgress.setAttribute("aria-hidden", "false");
        videoProgressFill.style.width = `${Math.max(0, Math.min(percent, 100))}%`;
        videoProgressText.textContent = message;
    }

    function hideVideoProgress() {
        videoProgress.classList.add("hidden");
        videoProgress.setAttribute("aria-hidden", "true");
        videoProgressFill.style.width = "0%";
    }

    function hideVideoProgressSoon() {
        window.setTimeout(hideVideoProgress, 1200);
    }
});
