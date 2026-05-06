document.addEventListener('DOMContentLoaded', () => {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const uploadStatus = document.getElementById('uploadStatus');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadProgressFill = document.getElementById('uploadProgressFill');
    const uploadProgressText = document.getElementById('uploadProgressText');
    const usePageRange = document.getElementById('usePageRange');
    const pageStart = document.getElementById('pageStart');
    const pageEnd = document.getElementById('pageEnd');
    const pageInfo = document.getElementById('pageInfo');
    const convertBtn = document.getElementById('convertBtn');
    const useSpellCheck = document.getElementById('useSpellCheck');
    const useTransformerSpell = document.getElementById('useTransformerSpell');
    const targetLanguage = document.getElementById('targetLanguage');
    const urduOptions = document.getElementById('urduOptions');
    const urduFont = document.getElementById('urduFont');
    const pipelineStages = document.getElementById('pipelineStages');

    targetLanguage.addEventListener('change', () => {
        if (targetLanguage.value === 'ur') {
            urduOptions.style.display = 'block';
            // Reload voices for Urdu
            if (window.loadVoices) {
                console.log('[UPLOAD] Loading Urdu voices...');
                window.loadVoices('ur');
            } else {
                console.warn('[UPLOAD] window.loadVoices not defined yet');
            }
        } else {
            urduOptions.style.display = 'none';
            // Reload English voices
            if (window.loadVoices) {
                window.loadVoices('en');
            }
        }
    });

    window.extractedChunks = [];
    window.cleanScript = '';
    window.urduScript = null;
    window.urduTextChunks = null;

    uploadZone.addEventListener('click', () => fileInput.click());
    usePageRange.addEventListener('change', () => {
        const enabled = usePageRange.checked;
        pageStart.disabled = !enabled;
        pageEnd.disabled = !enabled;
        if (enabled) {
            pageStart.value = pageStart.value || '1';
            pageEnd.value = pageEnd.value || pageStart.value || '1';
            pageStart.focus();
        }
    });

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFileUpload(fileInput.files[0]);
        }
    });

    async function handleFileUpload(file) {
        if (file.type !== 'application/pdf') {
            uploadStatus.textContent = 'Please upload a PDF file.';
            uploadStatus.classList.add('upload-error');
            hideUploadProgress();
            return;
        }

        uploadStatus.textContent = 'Preparing upload...';
        uploadStatus.classList.remove('upload-error');
        pageInfo.textContent = '';
        setUploadProgress(0, 'Uploading... (0%)', false);
        convertBtn.disabled = true;
        pipelineStages.classList.remove('hidden');
        updatePipelineStage('upload', 'active');

        const formData = new FormData();
        formData.append('file', file);

        try {
            // PHASE 1: UPLOAD
            updatePipelineStage('upload', 'completed');
            updatePipelineStage('extract', 'active');
            const uploadResult = await uploadPdf(formData);
            if (!uploadResult.success) throw new Error(uploadResult.error);

            const uploadId = uploadResult.data.upload_id;
            setUploadProgress(100, 'Upload complete.', false);
            uploadStatus.textContent = 'Upload complete. Extracting text...';

            // PHASE 2: EXTRACTION
            const extractParams = {
                upload_id: uploadId,
                use_spell_check: useSpellCheck.checked,
                use_transformer_spell: useTransformerSpell.checked,
                translate_to_urdu: targetLanguage.value === 'ur',
                target_language: targetLanguage.value
            };
            if (usePageRange.checked) {
                const startValue = parseInt(pageStart.value, 10);
                const endValue = parseInt(pageEnd.value, 10);
                if (Number.isInteger(startValue) && Number.isInteger(endValue)) {
                    extractParams.page_start = startValue;
                    extractParams.page_end = endValue;
                }
            }

            console.log('[UPLOAD] Sending to /extract:', extractParams);
            const extractInitResponse = await fetch('/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(extractParams)
            });
            const extractInitResult = await extractInitResponse.json();
            if (!extractInitResult.success) throw new Error(extractInitResult.error);

            const extractionJobId = extractInitResult.data.job_id;
            let spellStatus = useSpellCheck.checked ? 'spell check enabled' : 'spell check disabled';
            if (useSpellCheck.checked && useTransformerSpell.checked) spellStatus += ' + transformer';
            uploadStatus.textContent = `Extracting text (${spellStatus})...`;
            const extractionResult = await pollExtractionStatus(extractionJobId);

            // COMPLETION
            updatePipelineStage('extract', 'completed');
            updatePipelineStage('tts', 'active');
            window.extractedChunks = extractionResult.text_chunks;
            window.cleanScript = extractionResult.clean_script || '';
            window.urduScript = extractionResult.urdu_script || null;
            window.urduTextChunks = extractionResult.urdu_text_chunks || null;
            window.targetLanguage = targetLanguage.value;
            window.urduFont = urduFont ? urduFont.value : null;
            uploadStatus.textContent = 'Done.';
            setUploadProgress(100, 'Ready.', false);

            const words = extractionResult.word_count || 0;
            const pageLabel = extractionResult.page_range
                ? `Pages: ${extractionResult.page_range.start}-${extractionResult.page_range.end} of ${extractionResult.page_count}`
                : `Pages: ${extractionResult.page_count}`;
            pageInfo.textContent = `${pageLabel} | Words: ${words} | Chunks: ${extractionResult.text_chunks.length}`;
            convertBtn.disabled = false;

        } catch (error) {
            uploadStatus.textContent = `Error: ${error.message}`;
            uploadStatus.classList.add('upload-error');
            hideUploadProgress();
            pipelineStages.classList.add('hidden');
        }
    }

    function updatePipelineStage(stage, state) {
        const stageEl = document.getElementById(`stage${stage.charAt(0).toUpperCase() + stage.slice(1)}`);
        if (stageEl) {
            stageEl.classList.remove('active', 'completed');
            if (state) stageEl.classList.add(state);
        }
    }

    function uploadPdf(formData) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload');
            xhr.responseType = 'json';

            xhr.upload.addEventListener('progress', (event) => {
                if (event.lengthComputable) {
                    const uploadPercent = Math.round((event.loaded / event.total) * 100);
                    setUploadProgress(uploadPercent, `Uploading... (${uploadPercent}%)`, false);
                } else {
                    setUploadProgress(50, 'Uploading...', true);
                }
            });

            xhr.addEventListener('load', () => {
                const result = xhr.response || JSON.parse(xhr.responseText || '{}');
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(result);
                } else {
                    reject(new Error(result.error || `Upload failed with status ${xhr.status}`));
                }
            });

            xhr.addEventListener('error', () => reject(new Error('Network error during PDF upload.')));
            xhr.send(formData);
        });
    }

    async function pollExtractionStatus(jobId) {
        return new Promise((resolve, reject) => {
            const poll = async () => {
                try {
                    const response = await fetch(`/extract/status/${jobId}`);
                    const result = await response.json();

                    if (!result.success) {
                        reject(new Error(result.error));
                        return;
                    }

                    const data = result.data;
                    if (data.status === 'done') {
                        updatePipelineStage('extract', 'completed');
                        updatePipelineStage('tts', 'active');
                        resolve(data.result);
                    } else if (data.status === 'error') {
                        reject(new Error(data.error));
                    } else {
                        // Update extraction progress with phase-specific messages
                        const pagesDone = data.pages_done || 0;
                        const pagesTotal = data.pages_total || 0;
                        let message = 'Initializing extraction...';
                        if (data.status === 'extracting' && pagesTotal > 0) {
                            message = `Extracting text - page ${pagesDone} of ${pagesTotal}`;
                        } else if (data.status === 'spellchecking') {
                            const spellDone = data.spell_done || 0;
                            const spellTotal = data.spell_total || 0;
                            message = spellTotal > 0
                                ? `Spell checking ${spellDone} / ${spellTotal} sentences...`
                                : 'Spell checking...';
                        }
                        const percent = pagesTotal > 0 ? (pagesDone / pagesTotal) * 100 : 0;
                        setUploadProgress(percent, message, pagesTotal === 0);

                        setTimeout(poll, 1000);
                    }
                } catch (error) {
                    reject(error);
                }
            };
            poll();
        });
    }

    function setUploadProgress(percent, message, indeterminate) {
        uploadProgress.classList.remove('hidden');
        uploadProgress.setAttribute('aria-hidden', 'false');
        uploadProgress.classList.toggle('indeterminate', Boolean(indeterminate));
        uploadProgressFill.style.width = indeterminate
            ? '40%'
            : `${Math.max(0, Math.min(percent, 100))}%`;
        uploadProgressText.textContent = message;
    }

    function hideUploadProgress() {
        uploadProgress.classList.add('hidden');
        uploadProgress.setAttribute('aria-hidden', 'true');
        uploadProgress.classList.remove('indeterminate');
        uploadProgressFill.style.width = '0%';
    }
});
