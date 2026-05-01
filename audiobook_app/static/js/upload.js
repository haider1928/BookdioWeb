(function () {
  const dropZone = document.getElementById("uploadZone");
  const fileInput = document.getElementById("fileInput");
  const filenameEl = document.getElementById("filename");
  const pageCountEl = document.getElementById("pageCount");
  const textPreview = document.getElementById("textPreview");
  const statusEl = document.getElementById("uploadStatus");

  function setStatus(message, type) {
    statusEl.textContent = message;
    statusEl.classList.toggle("is-error", type === "error");
    statusEl.classList.toggle("is-success", type === "success");
  }

  function dispatchUploadComplete(data) {
    window.dispatchEvent(new CustomEvent("audiobook:upload-complete", { detail: data }));
  }

  async function uploadFile(file) {
    if (!file) {
      return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setStatus("Choose a PDF file.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setStatus("Extracting PDF text...", "");
    filenameEl.textContent = file.name;
    pageCountEl.textContent = "-";
    textPreview.value = "";
    window.dispatchEvent(new CustomEvent("audiobook:upload-start"));

    try {
      const response = await fetch("/upload", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || "Upload failed.");
      }

      filenameEl.textContent = payload.data.filename;
      pageCountEl.textContent = String(payload.data.page_count);
      textPreview.value = payload.data.text || "";
      setStatus("PDF text extracted.", "success");
      dispatchUploadComplete(payload.data);
    } catch (error) {
      pageCountEl.textContent = "-";
      textPreview.value = "";
      setStatus(error.message || "Upload failed.", "error");
      dispatchUploadComplete({ text: "" });
    }
  }

  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });

  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragging");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("is-dragging");
  });

  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
    uploadFile(event.dataTransfer.files[0]);
  });

  fileInput.addEventListener("change", () => {
    uploadFile(fileInput.files[0]);
  });
})();
