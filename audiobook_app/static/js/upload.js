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

    window.extractedChunks = [];
    window.cleanScript = '';

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

        const formData = new FormData();
        formData.append('file', file);

        try {
            // PHASE 1: UPLOAD
            const uploadResult = await uploadPdf(formData);
            if (!uploadResult.success) throw new Error(uploadResult.error);

            const uploadId = uploadResult.data.upload_id;
            setUploadProgress(100, 'Upload complete.', false);
            uploadStatus.textContent = 'Upload complete. Extracting text...';

            // PHASE 2: EXTRACTION
            const extractParams = { upload_id: uploadId };
            if (usePageRange.checked) {
                const startValue = parseInt(pageStart.value, 10);
                const endValue = parseInt(pageEnd.value, 10);
                if (Number.isInteger(startValue) && Number.isInteger(endValue)) {
                    extractParams.page_start = startValue;
                    extractParams.page_end = endValue;
                }
            }

            const extractInitResponse = await fetch('/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(extractParams)
            });
            const extractInitResult = await extractInitResponse.json();
            if (!extractInitResult.success) throw new Error(extractInitResult.error);

            const extractionJobId = extractInitResult.data.job_id;
            const extractionResult = await pollExtractionStatus(extractionJobId);

            // COMPLETION
            window.extractedChunks = extractionResult.text_chunks;
            window.cleanScript = extractionResult.clean_script || '';
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
                        resolve(data.result);
                    } else if (data.status === 'error') {
                        reject(new Error(data.error));
                    } else {
                        // Update extraction progress
                        const pagesDone = data.pages_done || 0;
                        const pagesTotal = data.pages_total || 0;
                        const message = pagesTotal > 0 
                            ? `Extracting text... page ${pagesDone} of ${pagesTotal}`
                            : 'Initializing extraction...';
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
