class KaraokePlayer {
    constructor(audioElement, containerDiv, jobId) {
        this.audio = audioElement;
        this.container = containerDiv;
        this.jobId = jobId;
        this.captions = [];
        this.activeLineIndex = -1;
        this.rafId = null;
        this.isCaptionsReady = false;
        this.layout = containerDiv.dataset.layout || "multi";
        this.activeStyle = containerDiv.dataset.activeStyle || "color";
        this.wordHighlight = containerDiv.dataset.wordHighlight !== 'false';

        this.handlePlay = this.handlePlay.bind(this);
        this.handlePause = this.handlePause.bind(this);
        this.handleSeeked = this.handleSeeked.bind(this);
        this.handleTimeUpdate = this.handleTimeUpdate.bind(this);
        this.handleEnded = this.handleEnded.bind(this);

        this.init();
    }

    async init() {
        this.playPauseBtn = document.getElementById("playPauseBtn");
        this.progressBarContainer = document.getElementById("progressBarContainer");
        this.progressBarFill = document.getElementById("progressBarFill");
        this.timeDisplay = document.getElementById("timeDisplay");

        this.playPauseBtn.addEventListener("click", () => {
            if (this.audio.paused) {
                this.audio.play();
            } else {
                this.audio.pause();
            }
        });

        this.progressBarContainer.addEventListener("click", (event) => {
            const rect = this.progressBarContainer.getBoundingClientRect();
            const pos = (event.clientX - rect.left) / rect.width;
            this.audio.currentTime = pos * this.audio.duration;
            this.sync(true);
        });

        this.audio.addEventListener("play", this.handlePlay);
        this.audio.addEventListener("pause", this.handlePause);
        this.audio.addEventListener("seeked", this.handleSeeked);
        this.audio.addEventListener("timeupdate", this.handleTimeUpdate);
        this.audio.addEventListener("ended", this.handleEnded);

        await this.pollAndLoadCaptions();
        this.updateUI();
    }

    async pollAndLoadCaptions() {
        const pollIntervalMs = 1200;
        while (!this.isCaptionsReady) {
            try {
                const response = await fetch(`/subtitles/${this.jobId}/captions`);
                if (response.status === 200) {
                    const result = await response.json();
                    if (result.success && Array.isArray(result.data.captions)) {
                        this.captions = result.data.captions;
                        this.renderLines();
                        this.isCaptionsReady = this.captions.length > 0;
                        this.sync(true);
                        return;
                    }
                }
            } catch (error) {
                console.error("Caption polling failed", error);
            }
            await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
        }
    }

    renderLines() {
        const existingScroller = document.getElementById("karaokeScroller");
        if (existingScroller) {
            existingScroller.remove();
        }

        const scroller = document.createElement("div");
        scroller.className = "karaoke-scroller";
        scroller.id = "karaokeScroller";

        this.captions.forEach((line, lineIdx) => {
            const lineDiv = document.createElement("div");
            lineDiv.className = "karaoke-line";
            lineDiv.id = `line-${lineIdx}`;
            
            if (line.word_entries && line.word_entries.length > 0) {
                line.word_entries.forEach((w, wIdx) => {
                    const span = document.createElement("span");
                    span.textContent = w.word;
                    span.id = `word-${lineIdx}-${wIdx}`;
                    lineDiv.appendChild(span);
                    if (wIdx < line.word_entries.length - 1) {
                        lineDiv.appendChild(document.createTextNode(" "));
                    }
                });
            } else {
                lineDiv.textContent = line.text;
            }
            
            scroller.appendChild(lineDiv);
        });

        this.container.prepend(scroller);
    }

    updateUI() {
        const current = this.audio.currentTime || 0;
        const duration = this.audio.duration || 0;
        const percent = duration > 0 ? (current / duration) * 100 : 0;
        this.progressBarFill.style.width = `${Math.max(0, Math.min(percent, 100))}%`;
        this.timeDisplay.textContent = `${this.formatTime(current)} / ${this.formatTime(duration)}`;
    }

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, "0")}`;
    }

    handlePlay() {
        this.playPauseBtn.textContent = "Pause";
        this.startSync();
    }

    handlePause() {
        this.playPauseBtn.textContent = "Play";
        this.stopSync();
    }

    handleSeeked() {
        this.sync(true);
        this.updateUI();
    }

    handleTimeUpdate() {
        this.updateUI();
        if (!this.rafId) {
            this.sync();
        }
    }

    handleEnded() {
        this.playPauseBtn.textContent = "Play";
        this.stopSync();
    }

    startSync() {
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
        }
        const loop = () => {
            this.sync();
            this.rafId = requestAnimationFrame(loop);
        };
        this.rafId = requestAnimationFrame(loop);
    }

    stopSync() {
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
        }
        this.rafId = null;
    }

    findActiveLine(currentMs) {
        if (!this.captions.length) {
            return -1;
        }

        let low = 0;
        let high = this.captions.length - 1;
        let lastKnown = 0;

        while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            const line = this.captions[mid];

            if (currentMs >= line.startMs && currentMs <= line.endMs) {
                return mid;
            }

            if (currentMs < line.startMs) {
                high = mid - 1;
            } else {
                lastKnown = mid;
                low = mid + 1;
            }
        }

        // If past all captions, return last index
        if (currentMs >= this.captions[this.captions.length - 1].endMs) {
            return this.captions.length - 1;
        }
        // If before all captions, return first index
        if (currentMs <= this.captions[0].startMs) {
            return 0;
        }
        // In a gap - return the caption that just ended
        return lastKnown;
    }

    sync(force = false) {
        if (!this.isCaptionsReady) {
            return;
        }

        // No offset needed - word timings from edge-tts are already accurate
        const currentMs = this.audio.currentTime * 1000;
        const activeLineIdx = this.findActiveLine(currentMs);
        if (activeLineIdx === -1) {
            return;
        }

        if (force || activeLineIdx !== this.activeLineIndex) {
            this.activeLineIndex = activeLineIdx;
            this.updateLineClasses(activeLineIdx);
        }

        // Word-level highlighting based on layout (only if wordHighlight is enabled)
        if (this.wordHighlight) {
            const activeLine = this.captions[activeLineIdx];
            if (activeLine && activeLine.word_entries) {
                if (this.layout === "typewriter") {
                    this.syncTypewriter(activeLineIdx, currentMs);
                } else {
                    this.syncWordHighlight(activeLineIdx, currentMs);
                }
            }
        }
    }

    syncTypewriter(activeLineIdx, currentMs) {
        const activeLine = this.captions[activeLineIdx];
        if (!activeLine || !activeLine.word_entries) return;

        // Hide non-active lines in typewriter mode
        this.captions.forEach((line, lineIdx) => {
            const lineEl = document.getElementById(`line-${lineIdx}`);
            if (!lineEl) return;
            if (lineIdx !== activeLineIdx) {
                lineEl.style.opacity = "0";
                lineEl.style.display = "none";
            } else {
                lineEl.style.display = "";
            }
        });

        // Word-level sync for typewriter
        activeLine.word_entries.forEach((w, wIdx) => {
            const wordEl = document.getElementById(`word-${activeLineIdx}-${wIdx}`);
            if (!wordEl) return;

            const isPast = currentMs > w.endMs;
            const isActive = currentMs >= w.startMs && currentMs <= w.endMs;
            const isFuture = currentMs < w.startMs;

            if (isPast) {
                wordEl.style.opacity = "0.6";
                wordEl.classList.remove("word-active");
            } else if (isActive) {
                wordEl.style.opacity = "1";
                wordEl.classList.add("word-active");
            } else {
                wordEl.style.opacity = "0.3";
                wordEl.classList.remove("word-active");
            }
        });
    }

    syncWordHighlight(activeLineIdx, currentMs) {
        const activeLine = this.captions[activeLineIdx];
        if (!activeLine || !activeLine.word_entries) return;

        activeLine.word_entries.forEach((w, wIdx) => {
            const wordEl = document.getElementById(`word-${activeLineIdx}-${wIdx}`);
            if (wordEl) {
                if (currentMs >= w.startMs && currentMs <= w.endMs) {
                    wordEl.classList.add("word-active");
                } else {
                    wordEl.classList.remove("word-active");
                }
            }
        });
    }

    updateLineClasses(activeIdx) {
        const scroller = document.getElementById("karaokeScroller");
        if (!scroller) {
            return;
        }

        this.captions.forEach((line, lineIdx) => {
            const lineEl = document.getElementById(`line-${lineIdx}`);
            if (!lineEl) {
                return;
            }

            lineEl.classList.remove("line-past", "line-active", "line-next", "line-future", "line-hidden");
            if (lineIdx < activeIdx - 1) {
                lineEl.classList.add("line-hidden");
            } else if (lineIdx === activeIdx - 1) {
                lineEl.classList.add("line-past");
            } else if (lineIdx === activeIdx) {
                lineEl.classList.add("line-active");
            } else if (lineIdx === activeIdx + 1) {
                lineEl.classList.add("line-next");
            } else {
                lineEl.classList.add("line-future");
            }
        });

        const activeLineEl = document.getElementById(`line-${activeIdx}`);
        if (!activeLineEl) {
            return;
        }

        const offset = activeLineEl.offsetTop - (this.container.offsetHeight * 0.45);
        scroller.style.transform = `translate3d(0, ${-offset}px, 0)`;
    }

    destroy() {
        this.stopSync();
        this.audio.removeEventListener("play", this.handlePlay);
        this.audio.removeEventListener("pause", this.handlePause);
        this.audio.removeEventListener("seeked", this.handleSeeked);
        this.audio.removeEventListener("timeupdate", this.handleTimeUpdate);
        this.audio.removeEventListener("ended", this.handleEnded);
    }
}

window.initKaraoke = (audioElement, jobId) => {
    const container = document.getElementById("karaokePanel");
    if (window.currentKaraoke) {
        window.currentKaraoke.destroy();
    }
    window.currentKaraoke = new KaraokePlayer(audioElement, container, jobId);
};
