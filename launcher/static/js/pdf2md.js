(() => {
    const $ = (s) => document.querySelector(s);
    const dropzone = $("#dropzone");
    const fileInput = $("#fileInput");
    const filenameEl = $("#filename");
    const progressSection = $("#progressSection");
    const progressBar = $("#progressBar");
    const progressStatus = $("#progressStatus");
    const progressPercent = $("#progressPercent");
    const resultSection = $("#resultSection");
    const statusMsg = $("#statusMsg");

    let taskId = null;

    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length) startConversion(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length) startConversion(fileInput.files[0]);
    });

    async function startConversion(file) {
        filenameEl.textContent = file.name;
        progressSection.style.display = "";
        resultSection.style.display = "none";
        statusMsg.innerHTML = "";
        progressBar.style.width = "0%";
        progressPercent.textContent = "0%";
        progressStatus.textContent = "Uploading...";

        const form = new FormData();
        form.append("file", file);

        const res = await fetch("/api/pdf2md/convert", { method: "POST", body: form });
        const data = await res.json();
        if (data.error) {
            showError(data.error);
            return;
        }

        taskId = data.task_id;
        listenProgress(taskId);
    }

    function listenProgress(id) {
        const es = new EventSource(`/api/pdf2md/progress/${id}`);
        es.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.keepalive) return;

            if (msg.error) {
                es.close();
                showError(msg.error);
                return;
            }

            if (msg.page !== undefined) {
                const pct = Math.round((msg.page / msg.total) * 100);
                progressBar.style.width = `${pct}%`;
                progressPercent.textContent = `${pct}%`;
                progressStatus.textContent = msg.status;
            }

            if (msg.done) {
                es.close();
                progressBar.style.width = "100%";
                progressPercent.textContent = "100%";
                progressStatus.textContent = "Done!";
                loadResult(id);
            }
        };
        es.onerror = () => {
            es.close();
            showError("Connection lost during conversion");
        };
    }

    async function loadResult(id) {
        const res = await fetch(`/api/pdf2md/preview/${id}`);
        const data = await res.json();
        if (data.error) {
            showError(data.error);
            return;
        }

        $("#inputSize").textContent = data.input_size;
        $("#outputSize").textContent = data.output_size;
        const reductionEl = $("#reduction");
        if (data.reduction > 0) {
            reductionEl.textContent = `${data.reduction}% smaller`;
            reductionEl.className = "stat-value stat-ok";
        } else if (data.reduction < 0) {
            reductionEl.textContent = `${Math.abs(data.reduction)}% larger`;
            reductionEl.className = "stat-value stat-warn";
        } else {
            reductionEl.textContent = "No change";
            reductionEl.className = "stat-value";
        }

        resultSection.style.display = "";

        // Preview toggle
        const previewPanel = $("#previewPanel");
        const toggleBtn = $("#togglePreview");
        const mdPreview = $("#mdPreview");
        mdPreview.textContent = data.markdown;

        toggleBtn.onclick = () => {
            const visible = previewPanel.style.display !== "none";
            previewPanel.style.display = visible ? "none" : "";
            toggleBtn.textContent = visible ? "Show Preview" : "Hide Preview";
        };
    }

    // Download
    $("#downloadBtn").addEventListener("click", () => {
        if (!taskId) return;
        window.location.href = `/api/pdf2md/download/${taskId}`;
    });

    function showError(msg) {
        statusMsg.innerHTML = `<div class="status-msg error">${msg}</div>`;
    }
})();
