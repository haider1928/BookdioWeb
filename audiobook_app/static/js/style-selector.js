class StyleSelector {
    constructor() {
        this.currentStyle = {
            bg: "#020617",
            bgStart: "#1e293b",
            inactiveColor: "#4b5563",
            activeColor: "#ffffff",
            activeStyle: "color",
            layout: "multi",
            font: "'Inter', sans-serif",
            fontSize: 48,  // Default font size in px
            wordHighlight: true,
            isCustom: false
        };

        this.fontSizeRange = document.getElementById("fontSizeRange");
        this.fontSizeValue = document.getElementById("fontSizeValue");

        this.panel = document.getElementById("karaokePanel");
        this.styleBtns = document.querySelectorAll(".style-btn");
        this.bgPicker = document.getElementById("bgColorPicker");
        this.inactivePicker = document.getElementById("inactiveColorPicker");
        this.activePicker = document.getElementById("activeColorPicker");
        this.fontSelect = document.getElementById("fontSelect");
        this.activeStyleSelect = document.getElementById("activeStyleSelect");
        this.layoutSelect = document.getElementById("layoutSelect");
        this.wordHighlightCheckbox = document.getElementById("wordHighlightCheckbox");

        this.init();
    }

    init() {
        // Preset button clicks
        this.styleBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                const styleName = btn.dataset.style;
                this.applyPreset(styleName);
                this.updateActiveButton(styleName);
            });
        });

        // Custom picker changes
        [this.bgPicker, this.inactivePicker, this.activePicker].forEach(picker => {
            picker.addEventListener("input", () => this.onCustomChange());
        });

        // Select changes
        [this.fontSelect, this.activeStyleSelect, this.layoutSelect].forEach(select => {
            select.addEventListener("change", () => this.onCustomChange());
        });

        // Font size slider
        if (this.fontSizeRange) {
            this.fontSizeRange.addEventListener("input", () => this.onCustomChange());
        }

        // Word highlight checkbox
        if (this.wordHighlightCheckbox) {
            this.wordHighlightCheckbox.addEventListener("change", () => this.onCustomChange());
        }

        // Apply default preset
        this.applyPreset("spotify");
        this.updateActiveButton("spotify");
    }

    getPresets() {
        return {
            spotify: {
                bg: "#121212", bgStart: "#1e293b",
                inactiveColor: "#535353", activeColor: "#1DB954",
                activeStyle: "color", layout: "single",
                font: "'Inter', sans-serif", fontSize: 48,
                wordHighlight: true
            },
            classic: {
                bg: "#0a0a0a", bgStart: "#1a1a1a",
                inactiveColor: "#666666", activeColor: "#FFD700",
                activeStyle: "underline", layout: "multi",
                font: "Arial, sans-serif", fontSize: 56,
                wordHighlight: true
            },
            neon: {
                bg: "#000000", bgStart: "#0a0a0a",
                inactiveColor: "#333333", activeColor: "#00FFFF",
                activeStyle: "glow", layout: "multi",
                font: "Arial, sans-serif", fontSize: 52,
                wordHighlight: true
            },
            minimal: {
                bg: "#FFFFFF", bgStart: "#f0f0f0",
                inactiveColor: "#CCCCCC", activeColor: "#E63946",
                activeStyle: "color", layout: "single",
                font: "'Inter', sans-serif", fontSize: 44,
                wordHighlight: true
            },
            block: {
                bg: "#1a1a2e", bgStart: "#16213e",
                inactiveColor: "#888888", activeColor: "#FF6B35",
                activeStyle: "block", layout: "multi",
                font: "Arial, sans-serif", fontSize: 50,
                wordHighlight: true
            }
        };
    }

    applyPreset(name) {
        const presets = this.getPresets();
        const preset = presets[name];
        if (!preset) return;

        this.currentStyle = { ...preset, isCustom: false };
        this.applyToPlayer();
        this.syncPickers();
    }

    onCustomChange() {
        this.currentStyle = {
            bg: this.bgPicker.value,
            bgStart: this.adjustLightness(this.bgPicker.value, 15),
            inactiveColor: this.inactivePicker.value,
            activeColor: this.activePicker.value,
            activeStyle: this.activeStyleSelect.value,
            layout: this.layoutSelect.value,
            font: this.fontSelect.value,
            fontSize: parseInt(this.fontSizeRange.value) || 48,
            wordHighlight: this.wordHighlightCheckbox ? this.wordHighlightCheckbox.checked : true,
            isCustom: true
        };
        if (this.fontSizeValue) {
            this.fontSizeValue.textContent = `${this.currentStyle.fontSize}px`;
        }
        this.applyToPlayer();
        this.clearActiveButton();
        this.updateHexLabels();
    }

    applyToPlayer() {
        const s = this.currentStyle;
        this.panel.style.setProperty("--karaoke-bg-start", s.bgStart);
        this.panel.style.setProperty("--karaoke-bg-end", s.bg);
        this.panel.style.setProperty("--karaoke-inactive", s.inactiveColor);
        this.panel.style.setProperty("--karaoke-active", s.activeColor);
        this.panel.style.setProperty("--karaoke-word-inactive", s.inactiveColor);
        this.panel.style.setProperty("--karaoke-word-active", s.activeColor);
        this.panel.style.setProperty("--karaoke-font", s.font);
        this.panel.style.setProperty("--karaoke-font-size", `${s.fontSize || 48}px`);
        this.panel.dataset.activeStyle = s.activeStyle;
        this.panel.dataset.layout = s.layout;
        this.panel.dataset.wordHighlight = s.wordHighlight;
        this.panel.style.fontFamily = s.font;
    }

    syncPickers() {
        const s = this.currentStyle;
        this.bgPicker.value = s.bg;
        this.inactivePicker.value = s.inactiveColor;
        this.activePicker.value = s.activeColor;
        this.fontSelect.value = s.font;
        this.activeStyleSelect.value = s.activeStyle;
        this.layoutSelect.value = s.layout;
        if (this.fontSizeRange) {
            this.fontSizeRange.value = s.fontSize || 48;
        }
        if (this.fontSizeValue) {
            this.fontSizeValue.textContent = `${s.fontSize || 48}px`;
        }
        if (this.wordHighlightCheckbox) {
            this.wordHighlightCheckbox.checked = s.wordHighlight;
        }
        this.updateHexLabels();
    }

    updateHexLabels() {
        const bgHex = document.getElementById("bgColorHex");
        const inactiveHex = document.getElementById("inactiveColorHex");
        const activeHex = document.getElementById("activeColorHex");
        if (bgHex) bgHex.textContent = this.bgPicker.value;
        if (inactiveHex) inactiveHex.textContent = this.inactivePicker.value;
        if (activeHex) activeHex.textContent = this.activePicker.value;
    }

    adjustLightness(hex, amount) {
        let r = parseInt(hex.slice(1, 3), 16);
        let g = parseInt(hex.slice(3, 5), 16);
        let b = parseInt(hex.slice(5, 7), 16);
        r = Math.min(255, r + amount);
        g = Math.min(255, g + amount);
        b = Math.min(255, b + amount);
        return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
    }

    updateActiveButton(name) {
        this.styleBtns.forEach(b => b.classList.toggle("active", b.dataset.style === name));
    }

    clearActiveButton() {
        this.styleBtns.forEach(b => b.classList.remove("active"));
    }

    getConfig() {
        const config = { ...this.currentStyle };
        // Ensure wordHighlight is included
        if (config.wordHighlight === undefined) {
            config.wordHighlight = true;
        }
        // Ensure fontSize is included
        if (config.fontSize === undefined) {
            config.fontSize = 48;
        }
        return config;
    }
}

window.styleSelector = null;
document.addEventListener("DOMContentLoaded", () => {
    window.styleSelector = new StyleSelector();
});
