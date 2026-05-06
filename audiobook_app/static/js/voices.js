let currentObjectUrl = null;
let previewCache = new Map();

window.loadVoices = async function(locale = 'en') {
    const voiceSelect = document.getElementById('voiceSelect');
    const previewStatus = document.getElementById('previewVoiceStatus');
    if (!voiceSelect) return;
    
    try {
        const response = await fetch(`/voices?locale=${locale}`);
        const result = await response.json();

        if (result.success && result.data.voices) {
            const allVoices = Object.values(result.data.voices).flat();
            if (allVoices.length === 0) {
                throw new Error('No voices available for this language');
            }
            
            voiceSelect.innerHTML = '';
            
            for (const [gender, voices] of Object.entries(result.data.voices)) {
                if (voices.length === 0) continue;
                
                const group = document.createElement('optgroup');
                group.label = gender;
                
                voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.ShortName;
                    option.textContent = `${voice.FriendlyName} (${voice.Locale})`;
                    group.appendChild(option);
                });
                
                voiceSelect.appendChild(group);
            }
            
            if (previewStatus) {
                previewStatus.textContent = 'Select a voice to preview.';
                previewStatus.classList.remove('preview-error');
            }
        } else {
            throw new Error(result.error || 'Failed to load voices');
        }
    } catch (error) {
        console.error('Error loading voices:', error);
        voiceSelect.innerHTML = '<option value="">Voices unavailable</option>';
        if (previewStatus) {
            previewStatus.textContent = `Error: ${error.message}`;
            previewStatus.classList.add('preview-error');
        }
    }
};

function setPreviewStatus(text, isError = false) {
    const previewStatus = document.getElementById('previewVoiceStatus');
    if (!previewStatus) return;
    previewStatus.textContent = text;
    previewStatus.classList.toggle('preview-error', Boolean(isError));
}

function speedString() {
    const speedRange = document.getElementById('speedRange');
    if (!speedRange) return '+0%';
    const val = parseInt(speedRange.value, 10);
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val}%`;
}

function cacheKey(voice, speed) {
    return `${voice}|${speed}`;
}

async function generatePreviewAudio(voice, speed) {
    const response = await fetch('/voices/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice, speed })
    });

    if (!response.ok) {
        let errMessage = `Preview generation failed (${response.status})`;
        try {
            const errJson = await response.json();
            if (errJson && errJson.error) {
                errMessage = errJson.error;
            }
        } catch (_) {}
        throw new Error(errMessage);
    }

    const blob = await response.blob();
    if (!blob || blob.size === 0) {
        throw new Error('Empty preview audio response');
    }
    return URL.createObjectURL(blob);
}

document.addEventListener('DOMContentLoaded', () => {
    const voiceSelect = document.getElementById('voiceSelect');
    const previewBtn = document.getElementById('previewVoiceBtn');
    const previewAudio = document.getElementById('voicePreviewAudio');
    const speedRange = document.getElementById('speedRange');

    if (!voiceSelect || !previewBtn || !previewAudio) {
        console.error('Voice UI elements not found');
        return;
    }

    previewBtn.addEventListener('click', async () => {
        const voice = voiceSelect.value;
        if (!voice) {
            setPreviewStatus('Please select a voice first.', true);
            return;
        }

        const speed = speedString();
        const key = cacheKey(voice, speed);
        previewBtn.disabled = true;
        setPreviewStatus(`Generating preview for ${voice} at ${speed}...`);

        try {
            let audioUrl = previewCache.get(key);
            if (!audioUrl) {
                audioUrl = await generatePreviewAudio(voice, speed);
                previewCache.set(key, audioUrl);
            }

            if (currentObjectUrl && currentObjectUrl !== audioUrl) {
                previewAudio.pause();
                previewAudio.currentTime = 0;
            }

            currentObjectUrl = audioUrl;
            previewAudio.src = audioUrl;
            await previewAudio.play();
            setPreviewStatus(`Playing preview: ${voice} (${speed})`);
        } catch (error) {
            setPreviewStatus(error.message, true);
        } finally {
            previewBtn.disabled = false;
        }
    });

    previewAudio.addEventListener('ended', () => {
        const voice = voiceSelect.value || 'voice';
        setPreviewStatus(`Preview ended for ${voice}.`);
    });

    voiceSelect.addEventListener('change', () => {
        setPreviewStatus('Ready to preview selected voice.');
    });

    window.loadVoices();
});