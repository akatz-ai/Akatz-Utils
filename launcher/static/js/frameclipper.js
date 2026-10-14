const frameEl = (id) => document.getElementById(id);
const urlInput = frameEl("frameYoutubeUrl");
const fileInput = frameEl("frameFile");
const loadButton = frameEl("frameLoadUrl");
const workspace = frameEl("frameWorkspace");
const status = frameEl("frameStatus");
const preview = frameEl("framePreview");
const placeholder = frameEl("framePreviewPlaceholder");
const seek = frameEl("frameSeek");
const timeInput = frameEl("frameTime");
const position = frameEl("framePosition");
const downloadButton = frameEl("frameDownload");
const formatSelect = frameEl("frameFormat");

let source = null;
let currentTime = 0;
let previewUrl = null;
let previewTimer = null;
let loadVersion = 0;
let previewVersion = 0;

function setStatus(message, error = false) {
    status.textContent = message;
    status.className = `frame-status${error ? " error" : ""}`;
    status.hidden = !message;
}

async function readJson(response) {
    if (!response.headers.get("content-type")?.includes("application/json")) {
        throw new Error(`The app returned ${response.status}. Restart Akatz Utils to load the latest version.`);
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
}

function formatTime(seconds) {
    const milliseconds = Math.round(seconds * 1000);
    const hours = Math.floor(milliseconds / 3600000);
    const minutes = Math.floor((milliseconds % 3600000) / 60000);
    const secs = Math.floor((milliseconds % 60000) / 1000);
    const fraction = String(milliseconds % 1000).padStart(3, "0");
    const clock = `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${fraction}`;
    return hours ? `${hours}:${clock}` : clock;
}

function parseTime(value) {
    const parts = value.trim().split(":");
    if (parts.length > 3 || parts.length < 1 || parts.some(part => !/^\d+(?:\.\d+)?$/.test(part))) return null;
    let seconds = 0;
    for (const part of parts) seconds = seconds * 60 + Number(part);
    return Number.isFinite(seconds) ? seconds : null;
}

function lastFrameTime() {
    if (!source) return 0;
    return Math.max(0, source.duration - (source.fps > 0 ? 0.5 / source.fps : 0.05));
}

function selectTime(value, refresh = true) {
    currentTime = Math.min(lastFrameTime(), Math.max(0, value));
    seek.value = String(currentTime);
    timeInput.value = formatTime(currentTime);
    position.textContent = formatTime(currentTime);
    if (refresh) schedulePreview();
}

function imageRequest(download = false) {
    if (!source) return null;
    return {
        source: source.source,
        upload_id: source.upload_id,
        url: source.url,
        time: currentTime,
        format: download ? formatSelect.value : "jpg",
        download,
    };
}

async function requestFrame(payload) {
    const response = await fetch("/api/frameclipper/frame", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(payload.download ? window.akatzExport.headers() : {}) },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        await readJson(response);
        throw new Error(`Frame request failed (${response.status})`);
    }
    return response;
}

function schedulePreview() {
    if (!source) return;
    clearTimeout(previewTimer);
    const version = ++previewVersion;
    previewTimer = setTimeout(() => showFrame(version), 180);
}

async function showFrame(version) {
    const payload = imageRequest();
    if (!payload) return;
    placeholder.textContent = "Loading frame…";
    placeholder.hidden = false;
    preview.hidden = true;
    try {
        const response = await requestFrame(payload);
        const blob = await response.blob();
        if (version !== previewVersion) return;
        const nextUrl = URL.createObjectURL(blob);
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = nextUrl;
        preview.onload = () => {
            if (version !== previewVersion) return;
            const frameSize = `${preview.naturalWidth} × ${preview.naturalHeight}`;
            frameEl("frameDetails").textContent = `${frameSize} • ${source.fps ? `${source.fps.toFixed(3)} fps` : "frame rate unknown"} • ${formatTime(source.duration)}`;
            preview.hidden = false;
            placeholder.hidden = true;
        };
        preview.src = nextUrl;
        setStatus("");
    } catch (error) {
        if (version !== previewVersion) return;
        placeholder.textContent = "Frame preview unavailable";
        setStatus(error.message || String(error), true);
    }
}

function useSource(metadata) {
    source = metadata;
    currentTime = 0;
    previewVersion++;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    preview.hidden = true;
    placeholder.hidden = false;
    frameEl("frameTitle").textContent = metadata.title;
    frameEl("frameDetails").textContent = `${metadata.width || "?"} × ${metadata.height || "?"} • ${formatTime(metadata.duration)}`;
    frameEl("frameDuration").textContent = formatTime(metadata.duration);
    seek.max = String(lastFrameTime());
    workspace.hidden = false;
    selectTime(0);
    setStatus("");
}

loadButton.addEventListener("click", async () => {
    const version = ++loadVersion;
    const url = urlInput.value.trim();
    if (!url) return setStatus("Paste a YouTube link first", true);
    loadButton.disabled = true;
    setStatus("Loading YouTube video…");
    try {
        const response = await fetch("/api/frameclipper/youtube", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }),
        });
        const metadata = await readJson(response);
        if (version === loadVersion) useSource(metadata);
    } catch (error) {
        if (version === loadVersion) setStatus(error.message || String(error), true);
    } finally {
        loadButton.disabled = false;
    }
});

urlInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadButton.click();
});

fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    const version = ++loadVersion;
    if (!file.name.toLowerCase().endsWith(".mp4") || file.size > 490 * 1024 * 1024) {
        return setStatus("Choose an MP4 file smaller than 490 MB", true);
    }
    const form = new FormData();
    form.append("file", file);
    setStatus("Uploading video…");
    try {
        const response = await fetch("/api/frameclipper/upload", { method: "POST", body: form });
        const metadata = await readJson(response);
        if (version === loadVersion) useSource(metadata);
    } catch (error) {
        if (version === loadVersion) setStatus(error.message || String(error), true);
    }
});

seek.addEventListener("input", () => selectTime(Number(seek.value), false));
seek.addEventListener("change", () => selectTime(Number(seek.value)));
timeInput.addEventListener("change", () => {
    const seconds = parseTime(timeInput.value);
    if (seconds === null) {
        timeInput.value = formatTime(currentTime);
        return setStatus("Enter a time like 00:12.345", true);
    }
    selectTime(seconds);
});

function stepFrame(direction) {
    if (!source) return;
    const fps = source.fps > 0 ? source.fps : 30;
    selectTime((Math.round(currentTime * fps) + direction) / fps);
}
frameEl("framePrevious").addEventListener("click", () => stepFrame(-1));
frameEl("frameNext").addEventListener("click", () => stepFrame(1));

downloadButton.addEventListener("click", async () => {
    if (!source) return;
    downloadButton.disabled = true;
    setStatus("Preparing full-resolution image…");
    try {
        const response = await requestFrame(imageRequest(true));
        if (await window.akatzExport.saved(response)) { setStatus(""); return; }
        const blob = await response.blob();
        const header = response.headers.get("content-disposition") || "";
        const encoded = header.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
        const fallback = header.match(/filename="([^"]+)"/)?.[1]
            || header.match(/filename=([^;]+)/)?.[1]?.trim()
            || `frame.${formatSelect.value}`;
        let filename = fallback;
        if (encoded) {
            try { filename = decodeURIComponent(encoded); } catch { /* Use the fallback name. */ }
        }
        const link = document.createElement("a");
        const objectUrl = URL.createObjectURL(blob);
        link.href = objectUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
        setStatus("");
    } catch (error) {
        setStatus(error.message || String(error), true);
    } finally {
        downloadButton.disabled = false;
    }
});

window.addEventListener("beforeunload", () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
});
