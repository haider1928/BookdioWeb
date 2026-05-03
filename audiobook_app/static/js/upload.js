document.addEventListener('DOMContentLoaded', () => {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const uploadStatus = document.getElementById('uploadStatus');
    const pageInfo = document.getElementById('pageInfo');
    const convertBtn = document.getElementById('convertBtn');

    window.extractedChunks = [];
    window.cleanScript = '';

    uploadZone.addEventListener('click', () => fileInput.click());

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
            return;
        }

        uploadStatus.textContent = 'Uploading and extracting text...';
        uploadStatus.classList.remove('upload-error');
        convertBtn.disabled = true;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.success) {
                window.extractedChunks = result.data.text_chunks;
                window.cleanScript = result.data.clean_script || '';
                uploadStatus.textContent = 'Text extracted successfully!';
                const words = result.data.word_count || 0;
                pageInfo.textContent = `Pages: ${result.data.page_count} | Words: ${words} | Chunks: ${result.data.text_chunks.length}`;
                convertBtn.disabled = false;
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            uploadStatus.textContent = `Error: ${error.message}`;
            uploadStatus.classList.add('upload-error');
        }
    }
});
