document.addEventListener("DOMContentLoaded", () => {
    const convertBtn = document.getElementById("convertBtn");
    const voiceSelect = document.getElementById("voiceSelect");
    const speedRange = document.getElementById("speedRange");
    const speedVal = document.getElementById("speedVal");
    const conversionStatus = document.getElementById("conversionStatus");
    const progressFill = document.getElementById("progressFill");
    const statusText = document.getElementById("statusText");
    const playerSection = document.getElementById("playerSection");
    const audioPlayer = document.getElementById("audioPlayer");
    const downloadOptions = document.getElementById("downloadOptions");
    const downloadAudioBtn = document.getElementById("downloadAudioBtn");
    const downloadVideoBtn = document.getElementById("downloadVideoBtn");

    let currentJobId = null;
    let pollInterval = null;
    let videoPollInterval = null;

    speedRange.addEventListener("input", () => {
        const value = parseInt(speedRange.value, 10);
        const sign = value >= 0 ? "+" : "";
        speedVal.textContent = `${sign}${value}%`;
    });

    convertBtn.addEventListener("click", async () => {
        if (!window.extractedChunks || window.extractedChunks.length === 0) {
            return;
        }

        const voice = voiceSelect.value;
        const speedValue = parseInt(speedRange.value, 10);
        const speed = `${speedValue >= 0 ? "+" : ""}${speedValue}%`;

        convertBtn.disabled = true;
        conversionStatus.classList.remove("hidden");
        statusText.textContent = "Initializing conversion pipeline...";
        progressFill.style.width = "0%";
        downloadOptions.classList.add("hidden");
        clearVideoPoll();

        try {
            const response = await fetch("/convert", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text_chunks: window.extractedChunks,
                    voice,
                    speed,
                }),
            });
            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error);
            }

            currentJobId = result.data.job_id;
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
        downloadVideoBtn.onclick = async () => {
            downloadVideoBtn.disabled = true;
            downloadVideoBtn.textContent = "Generating video...";
            await requestVideo(jobId);
        };
    }

    async function requestVideo(jobId) {
        try {
            const response = await fetch(`/download/${jobId}/video`);
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error);
            }

            if (result.data.video_status === "done" && result.data.download_url) {
                window.location.href = result.data.download_url;
                downloadVideoBtn.disabled = false;
                downloadVideoBtn.textContent = "Download Video";
                return;
            }

            startVideoPolling(jobId);
        } catch (error) {
            downloadVideoBtn.disabled = false;
            downloadVideoBtn.textContent = "Download Video";
            alert(`Video export failed: ${error.message}`);
        }
    }

    function startVideoPolling(jobId) {
        clearVideoPoll();
        videoPollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/download/${jobId}/video/status`);
                const result = await response.json();
                if (!result.success) {
                    return;
                }

                const { video_status: videoStatus, video_error: videoError, download_url: downloadUrl } = result.data;
                if (videoStatus === "done" && downloadUrl) {
                    clearVideoPoll();
                    downloadVideoBtn.disabled = false;
                    downloadVideoBtn.textContent = "Download Video";
                    window.location.href = downloadUrl;
                    return;
                }

                if (videoStatus === "error") {
                    clearVideoPoll();
                    downloadVideoBtn.disabled = false;
                    downloadVideoBtn.textContent = "Download Video";
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
});
