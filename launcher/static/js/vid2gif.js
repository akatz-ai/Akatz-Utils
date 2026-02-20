(() => {
    const $ = (s) => document.querySelector(s);
    const dropzone = $("#dropzone");
    const fileInput = $("#fileInput");
    const filenameEl = $("#filename");
    const optionsSection = $("#optionsSection");
    const progressSection = $("#progressSection");
    const progressBar = $("#progressBar");
    const progressStatus = $("#progressStatus");
    const resultSection = $("#resultSection");
    const statusMsg = $("#statusMsg");

    let selectedFile = null;
    let taskId = null;

    // Dropzone
    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length) selectFile(fileInput.files[0]);
    });

    function selectFile(file) {
        selectedFile = file;
        filenameEl.textContent = file.name;
        optionsSection.style.display = "";
        resultSection.style.display = "none";
        statusMsg.innerHTML = "";
    }

    // Dimension toggle
    const useOriginal = $("#useOriginal");
    const dimControls = $("#dimControls");
    useOriginal.addEventListener("change", () => {
        dimControls.style.display = useOriginal.checked ? "none" : "";
    });

    // Convert
    $("#convertBtn").addEventListener("click", async () => {
        if (!selectedFile) return;

        const form = new FormData();
        form.append("file", selectedFile);
        form.append("duration", $("#duration").value);
        form.append("target_size_mb", $("#targetSize").value);
        form.append("aspect_mode", document.querySelector('input[name="aspect"]:checked').value);

        if (!useOriginal.checked) {
            const w = $("#outWidth").value;
            const h = $("#outHeight").value;
            if (w) form.append("width", w);
            if (h) form.append("height", h);
        }

        progressSection.style.display = "";
        resultSection.style.display = "none";
        statusMsg.innerHTML = "";
        progressBar.style.width = "0%";
        progressStatus.textContent = "Uploading...";
        $("#convertBtn").disabled = true;

        const res = await fetch("/api/vid2gif/convert", { method: "POST", body: form });
        const data = await res.json();
        if (data.error) {
            showError(data.error);
            $("#convertBtn").disabled = false;
            return;
        }

        taskId = data.task_id;
        listenProgress(taskId);
    });

    function listenProgress(id) {
        // Use indeterminate progress (pulse animation) since vid2gif doesn't give page-by-page
        progressBar.style.width = "100%";
        progressBar.style.opacity = "0.6";
        progressBar.style.animation = "pulse 1.5s ease-in-out infinite";

        const es = new EventSource(`/api/vid2gif/progress/${id}`);
        es.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.keepalive) return;

            if (msg.error) {
                es.close();
                showError(msg.error);
                $("#convertBtn").disabled = false;
                progressBar.style.animation = "";
                return;
            }

            if (msg.status) {
                progressStatus.textContent = msg.status;
            }

            if (msg.done) {
                es.close();
                progressBar.style.animation = "";
                progressBar.style.opacity = "1";
                progressBar.style.width = "100%";
                progressStatus.textContent = "Done!";
                showResult(id, msg.size_mb);
                $("#convertBtn").disabled = false;
            }
        };
        es.onerror = () => {
            es.close();
            showError("Connection lost during conversion");
            $("#convertBtn").disabled = false;
            progressBar.style.animation = "";
        };
    }

    function showResult(id, sizeMb) {
        resultSection.style.display = "";
        $("#gifSize").textContent = `${sizeMb} MB`;

        // Show GIF preview
        const preview = $("#gifPreview");
        preview.src = `/api/vid2gif/download/${id}`;
        preview.style.display = "";
    }

    $("#downloadBtn").addEventListener("click", () => {
        if (!taskId) return;
        window.location.href = `/api/vid2gif/download/${taskId}`;
    });

    function showError(msg) {
        statusMsg.innerHTML = `<div class="status-msg error">${msg}</div>`;
    }

    // Add pulse keyframe
    const style = document.createElement("style");
    style.textContent = `@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }`;
    document.head.appendChild(style);
})();
