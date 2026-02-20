(() => {
    const $ = (s) => document.querySelector(s);
    const dropzone = $("#dropzone");
    const fileInput = $("#fileInput");
    const filenameEl = $("#filename");
    const editor = $("#editor");

    const widthSlider = $("#widthSlider");
    const heightSlider = $("#heightSlider");
    const widthVal = $("#widthVal");
    const heightVal = $("#heightVal");
    const aspectLock = $("#aspectLock");
    const modeGroup = $("#modeGroup");

    const qualitySlider = $("#qualitySlider");
    const qualityVal = $("#qualityVal");
    const targetSlider = $("#targetSlider");
    const targetVal = $("#targetVal");

    const previewArea = $("#previewArea");
    const exportBtn = $("#exportBtn");
    const exportFormat = $("#exportFormat");

    let fileId = null;
    let origWidth = 0;
    let origHeight = 0;
    let aspectRatio = 1;
    let updatingSliders = false;
    let previewTimeout = null;

    // Dropzone handling
    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length) uploadFile(fileInput.files[0]);
    });

    async function uploadFile(file) {
        filenameEl.textContent = `Uploading ${file.name}...`;
        const form = new FormData();
        form.append("file", file);

        const res = await fetch("/api/imgsizer/upload", { method: "POST", body: form });
        const data = await res.json();
        if (data.error) {
            filenameEl.textContent = `Error: ${data.error}`;
            return;
        }

        fileId = data.file_id;
        origWidth = data.width;
        origHeight = data.height;
        aspectRatio = origWidth / origHeight;

        filenameEl.textContent = `${data.filename} (${origWidth}x${origHeight}, ${formatBytes(data.original_bytes)})`;

        widthSlider.max = Math.max(5000, origWidth * 2);
        heightSlider.max = Math.max(5000, origHeight * 2);
        widthSlider.value = origWidth;
        heightSlider.value = origHeight;
        widthVal.textContent = `${origWidth} px`;
        heightVal.textContent = `${origHeight} px`;

        editor.style.display = "";
        exportBtn.disabled = false;
        requestPreview();
    }

    // Sliders
    widthSlider.addEventListener("input", () => {
        if (updatingSliders) return;
        const w = parseInt(widthSlider.value);
        widthVal.textContent = `${w} px`;
        if (aspectLock.checked) {
            updatingSliders = true;
            const h = Math.round(w / aspectRatio);
            heightSlider.value = h;
            heightVal.textContent = `${h} px`;
            updatingSliders = false;
        }
        schedulePreview();
    });

    heightSlider.addEventListener("input", () => {
        if (updatingSliders) return;
        const h = parseInt(heightSlider.value);
        heightVal.textContent = `${h} px`;
        if (aspectLock.checked) {
            updatingSliders = true;
            const w = Math.round(h * aspectRatio);
            widthSlider.value = w;
            widthVal.textContent = `${w} px`;
            updatingSliders = false;
        }
        schedulePreview();
    });

    qualitySlider.addEventListener("input", () => {
        qualityVal.textContent = `${qualitySlider.value}%`;
        schedulePreview();
    });

    targetSlider.addEventListener("input", () => {
        const kb = parseInt(targetSlider.value);
        targetVal.textContent = kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} KB`;
    });

    aspectLock.addEventListener("change", () => {
        modeGroup.style.display = aspectLock.checked ? "none" : "";
        if (aspectLock.checked && fileId) {
            const w = parseInt(widthSlider.value);
            const h = Math.round(w / aspectRatio);
            heightSlider.value = h;
            heightVal.textContent = `${h} px`;
            schedulePreview();
        }
    });

    // Mode radios
    document.querySelectorAll('input[name="mode"]').forEach((r) =>
        r.addEventListener("change", () => schedulePreview())
    );

    // Presets
    document.querySelectorAll("[data-preset]").forEach((btn) => {
        btn.addEventListener("click", () => {
            if (!fileId) return;
            const [w, h, q] = btn.dataset.preset.split(",").map(Number);
            widthSlider.value = w;
            heightSlider.value = h;
            qualitySlider.value = q;
            widthVal.textContent = `${w} px`;
            heightVal.textContent = `${h} px`;
            qualityVal.textContent = `${q}%`;
            if (aspectLock.checked) aspectRatio = w / h;
            requestPreview();
        });
    });

    // Auto-adjust
    $("#autoAdjust").addEventListener("click", async () => {
        if (!fileId) return;
        const mode = document.querySelector('input[name="mode"]:checked').value;
        const res = await fetch("/api/imgsizer/auto-adjust", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file_id: fileId,
                width: parseInt(widthSlider.value),
                height: parseInt(heightSlider.value),
                mode,
                target_kb: parseInt(targetSlider.value),
            }),
        });
        const data = await res.json();
        if (data.error) return;

        qualitySlider.value = data.quality;
        qualityVal.textContent = `${data.quality}%`;
        if (data.scale < 1) {
            widthSlider.value = data.width;
            heightSlider.value = data.height;
            widthVal.textContent = `${data.width} px`;
            heightVal.textContent = `${data.height} px`;
        }
        requestPreview();
    });

    // Export
    exportBtn.addEventListener("click", async () => {
        if (!fileId) return;
        const mode = document.querySelector('input[name="mode"]:checked').value;
        const res = await fetch("/api/imgsizer/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file_id: fileId,
                width: parseInt(widthSlider.value),
                height: parseInt(heightSlider.value),
                quality: parseInt(qualitySlider.value),
                mode,
                format: exportFormat.value,
            }),
        });
        if (!res.ok) return;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = res.headers.get("Content-Disposition")?.match(/filename="?(.+?)"?$/)?.[1] || "image.jpg";
        a.click();
        URL.revokeObjectURL(url);
    });

    // Preview debounce
    function schedulePreview() {
        clearTimeout(previewTimeout);
        previewTimeout = setTimeout(requestPreview, 200);
    }

    async function requestPreview() {
        if (!fileId) return;
        const mode = document.querySelector('input[name="mode"]:checked').value;
        const body = {
            file_id: fileId,
            width: parseInt(widthSlider.value),
            height: parseInt(heightSlider.value),
            quality: parseInt(qualitySlider.value),
            mode,
        };

        const res = await fetch("/api/imgsizer/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

        if (!res.ok) return;

        const estBytes = parseInt(res.headers.get("X-Estimated-Bytes") || "0");
        const rW = res.headers.get("X-Width") || body.width;
        const rH = res.headers.get("X-Height") || body.height;

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);

        previewArea.innerHTML = `<img src="${url}" alt="Preview">`;

        // Update stats
        $("#statDims").textContent = `${rW} x ${rH} px`;
        $("#statSize").textContent = formatBytes(estBytes);
        $("#statQuality").textContent = `${qualitySlider.value}%`;

        const targetKb = parseInt(targetSlider.value);
        const estKb = estBytes / 1024;
        const diff = estKb - targetKb;
        const statTarget = $("#statTarget");
        if (diff > 0) {
            statTarget.textContent = `${diff.toFixed(1)} KB over`;
            statTarget.className = "stat-value stat-over";
        } else {
            statTarget.textContent = `${Math.abs(diff).toFixed(1)} KB under`;
            statTarget.className = "stat-value stat-ok";
        }
    }

    function formatBytes(b) {
        if (b >= 1048576) return `${(b / 1048576).toFixed(2)} MB`;
        if (b >= 1024) return `${(b / 1024).toFixed(1)} KB`;
        return `${b} B`;
    }
})();
