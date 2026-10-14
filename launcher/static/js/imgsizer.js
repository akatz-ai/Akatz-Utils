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

    // Crop DOM elements
    const cropContainer = $("#cropContainer");
    const cropBox = $("#cropBox");
    const cropSizeLabel = $("#cropSizeLabel");
    const cropToggle = $("#cropToggle");
    const cropReset = $("#cropReset");
    const cropInfo = $("#cropInfo");
    const cropInfoText = $("#cropInfoText");

    let fileId = null;
    let origWidth = 0;
    let origHeight = 0;
    let aspectRatio = 1;
    let updatingSliders = false;
    let previewTimeout = null;

    // Crop state
    let cropActive = false;   // crop mode UI is active (overlay visible)
    let cropRect = null;      // {x, y, w, h} in original-image pixels, or null
    let cropCommitted = false; // crop has been committed (deactivated with a selection)

    // Drag state
    let dragType = null;   // "new", "move", or handle direction like "se"
    let dragStart = null;  // {px, py} in CSS px relative to preview img
    let dragOrigRect = null; // copy of cropRect at drag start (original-image px)

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

        // Reset crop state on new upload
        resetCrop();

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

    // Presets — clear crop when applying a preset
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
            resetCrop();
            requestPreview();
        });
    });

    // Auto-adjust
    $("#autoAdjust").addEventListener("click", async () => {
        if (!fileId) return;
        const mode = document.querySelector('input[name="mode"]:checked').value;
        const body = {
            file_id: fileId,
            width: parseInt(widthSlider.value),
            height: parseInt(heightSlider.value),
            mode,
            target_kb: parseInt(targetSlider.value),
        };
        addCropParams(body);
        const res = await fetch("/api/imgsizer/auto-adjust", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
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
        const body = {
            file_id: fileId,
            width: parseInt(widthSlider.value),
            height: parseInt(heightSlider.value),
            quality: parseInt(qualitySlider.value),
            mode,
            format: exportFormat.value,
        };
        addCropParams(body);
        const res = await fetch("/api/imgsizer/export", {
            method: "POST",
            headers: { "Content-Type": "application/json", ...window.akatzExport.headers() },
            body: JSON.stringify(body),
        });
        if (await window.akatzExport.saved(res)) return;
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

        // In crop-active mode, show the full original image for overlay drawing
        if (cropActive) {
            await requestFullPreview();
            return;
        }

        const mode = document.querySelector('input[name="mode"]:checked').value;
        const body = {
            file_id: fileId,
            width: parseInt(widthSlider.value),
            height: parseInt(heightSlider.value),
            quality: parseInt(qualitySlider.value),
            mode,
        };
        addCropParams(body);

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

    // Fetch full-resolution preview (no crop/resize) for crop overlay mode
    async function requestFullPreview() {
        if (!fileId) return;
        const body = {
            file_id: fileId,
            width: origWidth,
            height: origHeight,
            quality: 80,
            mode: "stretch",
        };
        const res = await fetch("/api/imgsizer/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) return;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        previewArea.innerHTML = `<img src="${url}" alt="Preview" draggable="false">`;
        // After image loads, position existing crop overlay if any
        const img = previewArea.querySelector("img");
        img.addEventListener("load", () => {
            if (cropRect) renderCropOverlay();
        });
    }

    // --- Crop Tool ---

    function addCropParams(body) {
        if (cropRect && cropCommitted) {
            // Only send crop if it's not the full image
            if (cropRect.x !== 0 || cropRect.y !== 0 || cropRect.w !== origWidth || cropRect.h !== origHeight) {
                body.crop_x = Math.round(cropRect.x);
                body.crop_y = Math.round(cropRect.y);
                body.crop_w = Math.round(cropRect.w);
                body.crop_h = Math.round(cropRect.h);
            }
        }
    }

    function resetCrop() {
        cropRect = null;
        cropCommitted = false;
        cropActive = false;
        cropToggle.classList.remove("active");
        cropContainer.classList.remove("crop-active");
        cropBox.style.display = "none";
        cropReset.style.display = "none";
        cropInfo.style.display = "none";
    }

    cropToggle.addEventListener("click", () => {
        if (!fileId) return;
        if (cropActive) {
            deactivateCropMode();
        } else {
            activateCropMode();
        }
    });

    cropReset.addEventListener("click", () => {
        if (!fileId) return;
        const wasCommitted = cropCommitted;
        resetCrop();
        if (wasCommitted) {
            // Restore sliders to original dims
            widthSlider.value = origWidth;
            heightSlider.value = origHeight;
            widthVal.textContent = `${origWidth} px`;
            heightVal.textContent = `${origHeight} px`;
            aspectRatio = origWidth / origHeight;
            requestPreview();
        }
    });

    function activateCropMode() {
        cropActive = true;
        cropCommitted = false;
        cropToggle.classList.add("active");
        cropContainer.classList.add("crop-active");
        cropReset.style.display = "";
        // Show full image for overlay
        requestFullPreview();
    }

    function deactivateCropMode() {
        cropActive = false;
        cropToggle.classList.remove("active");
        cropContainer.classList.remove("crop-active");
        cropBox.style.display = "none";

        if (cropRect && (cropRect.w >= 10 && cropRect.h >= 10)) {
            cropCommitted = true;
            // Update sliders to cropped dimensions
            const cw = Math.round(cropRect.w);
            const ch = Math.round(cropRect.h);
            widthSlider.value = cw;
            heightSlider.value = ch;
            widthVal.textContent = `${cw} px`;
            heightVal.textContent = `${ch} px`;
            aspectRatio = cw / ch;
            cropInfo.style.display = "";
            cropInfoText.textContent = `Crop: ${cw} x ${ch} px`;
            cropReset.style.display = "";
        } else {
            cropRect = null;
            cropCommitted = false;
            cropInfo.style.display = "none";
            cropReset.style.display = "none";
        }
        requestPreview();
    }

    // Coordinate mapping: display CSS pixels <-> original image pixels
    function getPreviewImg() {
        return previewArea.querySelector("img");
    }

    function displayToOrig(dxPx, dyPx) {
        const img = getPreviewImg();
        if (!img) return { x: 0, y: 0 };
        const scale = origWidth / img.clientWidth;
        return { x: dxPx * scale, y: dyPx * scale };
    }

    function origToDisplay(ox, oy) {
        const img = getPreviewImg();
        if (!img) return { x: 0, y: 0 };
        const scale = img.clientWidth / origWidth;
        return { x: ox * scale, y: oy * scale };
    }

    function getImgOffset() {
        const img = getPreviewImg();
        if (!img) return { left: 0, top: 0 };
        const containerRect = cropContainer.getBoundingClientRect();
        const imgRect = img.getBoundingClientRect();
        return {
            left: imgRect.left - containerRect.left,
            top: imgRect.top - containerRect.top,
        };
    }

    function renderCropOverlay() {
        if (!cropRect || !cropActive) {
            cropBox.style.display = "none";
            return;
        }
        const img = getPreviewImg();
        if (!img) return;

        const offset = getImgOffset();
        const topLeft = origToDisplay(cropRect.x, cropRect.y);
        const size = origToDisplay(cropRect.w, cropRect.h);

        cropBox.style.display = "";
        cropBox.style.left = (offset.left + topLeft.x) + "px";
        cropBox.style.top = (offset.top + topLeft.y) + "px";
        cropBox.style.width = size.x + "px";
        cropBox.style.height = size.y + "px";

        cropSizeLabel.textContent = `${Math.round(cropRect.w)} x ${Math.round(cropRect.h)}`;
    }

    // Clamp cropRect to image bounds
    function clampCropRect() {
        if (!cropRect) return;
        cropRect.x = Math.max(0, Math.min(cropRect.x, origWidth - 10));
        cropRect.y = Math.max(0, Math.min(cropRect.y, origHeight - 10));
        cropRect.w = Math.max(10, Math.min(cropRect.w, origWidth - cropRect.x));
        cropRect.h = Math.max(10, Math.min(cropRect.h, origHeight - cropRect.y));
    }

    // Pointer events for crop drawing/resizing/moving
    cropContainer.addEventListener("pointerdown", (e) => {
        if (!cropActive) return;
        const img = getPreviewImg();
        if (!img) return;

        const handle = e.target.closest(".crop-handle");
        const isBox = e.target.closest(".crop-box") && !handle;

        const containerRect = cropContainer.getBoundingClientRect();
        const px = e.clientX - containerRect.left;
        const py = e.clientY - containerRect.top;

        if (handle) {
            // Resize via handle
            dragType = handle.dataset.dir;
            dragStart = { px, py };
            dragOrigRect = { ...cropRect };
        } else if (isBox) {
            // Move
            dragType = "move";
            dragStart = { px, py };
            dragOrigRect = { ...cropRect };
        } else {
            // Check if click is on the image area
            const offset = getImgOffset();
            const imgW = img.clientWidth;
            const imgH = img.clientHeight;
            if (px < offset.left || px > offset.left + imgW || py < offset.top || py > offset.top + imgH) return;

            // New crop draw
            dragType = "new";
            const orig = displayToOrig(px - offset.left, py - offset.top);
            cropRect = { x: orig.x, y: orig.y, w: 0, h: 0 };
            dragStart = { px, py };
            dragOrigRect = { ...cropRect };
        }

        e.preventDefault();
        cropContainer.setPointerCapture(e.pointerId);
    });

    cropContainer.addEventListener("pointermove", (e) => {
        if (!dragType) return;
        const containerRect = cropContainer.getBoundingClientRect();
        const px = e.clientX - containerRect.left;
        const py = e.clientY - containerRect.top;
        const dx = px - dragStart.px;
        const dy = py - dragStart.py;

        const img = getPreviewImg();
        if (!img) return;
        const scale = origWidth / img.clientWidth;
        const odx = dx * scale;
        const ody = dy * scale;

        if (dragType === "new") {
            const offset = getImgOffset();
            const orig = displayToOrig(px - offset.left, py - offset.top);
            // Allow drawing in any direction
            const x1 = dragOrigRect.x;
            const y1 = dragOrigRect.y;
            const x2 = Math.max(0, Math.min(orig.x, origWidth));
            const y2 = Math.max(0, Math.min(orig.y, origHeight));
            cropRect = {
                x: Math.min(x1, x2),
                y: Math.min(y1, y2),
                w: Math.abs(x2 - x1),
                h: Math.abs(y2 - y1),
            };
        } else if (dragType === "move") {
            cropRect.x = dragOrigRect.x + odx;
            cropRect.y = dragOrigRect.y + ody;
            cropRect.w = dragOrigRect.w;
            cropRect.h = dragOrigRect.h;
            // Clamp position
            cropRect.x = Math.max(0, Math.min(cropRect.x, origWidth - cropRect.w));
            cropRect.y = Math.max(0, Math.min(cropRect.y, origHeight - cropRect.h));
        } else {
            // Handle resize
            resizeByHandle(dragType, odx, ody);
        }

        clampCropRect();
        renderCropOverlay();
    });

    cropContainer.addEventListener("pointerup", (e) => {
        if (!dragType) return;
        dragType = null;
        dragStart = null;
        dragOrigRect = null;
        clampCropRect();
        renderCropOverlay();
    });

    function resizeByHandle(dir, odx, ody) {
        const r = dragOrigRect;
        let x = r.x, y = r.y, w = r.w, h = r.h;

        if (dir.includes("w")) {
            x = r.x + odx;
            w = r.w - odx;
        }
        if (dir.includes("e")) {
            w = r.w + odx;
        }
        if (dir.includes("n")) {
            y = r.y + ody;
            h = r.h - ody;
        }
        if (dir.includes("s")) {
            h = r.h + ody;
        }

        // Enforce minimum and prevent inversion
        if (w < 10) {
            if (dir.includes("w")) { x = r.x + r.w - 10; }
            w = 10;
        }
        if (h < 10) {
            if (dir.includes("n")) { y = r.y + r.h - 10; }
            h = 10;
        }

        cropRect = { x, y, w, h };
    }

    function formatBytes(b) {
        if (b >= 1048576) return `${(b / 1048576).toFixed(2)} MB`;
        if (b >= 1024) return `${(b / 1024).toFixed(1)} KB`;
        return `${b} B`;
    }
})();
