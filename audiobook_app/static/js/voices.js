document.addEventListener('DOMContentLoaded', () => {
    const voiceSelect = document.getElementById('voiceSelect');

    async function loadVoices() {
        try {
            const response = await fetch('/voices');
            const result = await response.json();

            if (result.success) {
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
            }
        } catch (error) {
            console.error('Error loading voices:', error);
        }
    }

    loadVoices();
});
