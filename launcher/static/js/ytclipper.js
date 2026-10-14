const $ = (id) => document.getElementById(id);

const urlInput = $("ytUrlInput");
const loadBtn = $("ytLoadBtn");
const playerSection = $("ytPlayerSection");
const controlsSection = $("ytControlsSection");
const statusEl = $("ytStatus");
const formatSelect = $("ytFormatSelect");
const fastMP4 = $("ytFastMP4");
// Apply the default even when the running server has an older template cached.
fastMP4.checked = true;
const downloadBtn = $("ytDownloadBtn");
const previewNotice = $("ytPreviewNotice");
const setStartBtn = $("ytSetStartBtn");
const setEndBtn = $("ytSetEndBtn");

const startInput = $("ytStartInput");
const endInput = $("ytEndInput");
const timeline = $("ytTimeline");
const overview = $("ytTimelineOverview");
const overviewSelection = $("ytOverviewSelection");
const overviewViewport = $("ytOverviewViewport");
const selection = $("ytTimelineSelection");
const handleStart = $("ytHandleStart");
const handleEnd = $("ytHandleEnd");
const timelinePlayhead = $("ytTimelinePlayhead");
const overviewPlayhead = $("ytOverviewPlayhead");
const zoomLevel = $("ytZoomLevel");

let currentUrl = "";
let apiLoaded = false;
let apiReady = null;
let player = null;
let pollTimer = null;

let duration = 0;
let startTime = 0;
let endTime = 0;
let viewStart = 0;
let viewEnd = 0;
let controlsInitialized = false;
let loadSequence = 0;

let dragMode = null;
let dragStartX = 0;
let dragStartValue = 0;
let dragStartValue2 = 0;

const MIN_VIEW_DURATION = 5;

function showStatus(message, type) {
    statusEl.textContent = message;
    statusEl.className = `yt-status ${type}`;
    statusEl.hidden = false;
}

function hideStatus() {
    statusEl.hidden = true;
}

function extractVideoId(url) {
    return url.match(/(?:youtube\.com\/(?:watch\?.*v=|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/)?.[1] ?? null;
}

function loadYouTubeAPI() {
    if (apiReady) return apiReady;
    apiReady = new Promise((resolve, reject) => {
        if (apiLoaded && window.YT?.Player) {
            resolve();
            return;
        }
        window.onYouTubeIframeAPIReady = () => {
            apiLoaded = true;
            resolve();
        };
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        script.onerror = () => {
            apiReady = null;
            reject(new Error("YouTube preview could not load"));
        };
        document.head.appendChild(script);
    });
    return apiReady;
}

function showPreviewUnavailable() {
    playerSection.hidden = true;
    setStartBtn.disabled = true;
    setEndBtn.disabled = true;
    previewNotice.textContent = "YouTube preview unavailable. Choose MP4 to download the full video, or set start/end times manually.";
    previewNotice.hidden = false;
}

function loadVideo(videoId, sequence) {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
    if (player) {
        player.destroy();
        player = null;
    }

    let ready = false;
    const timeout = setTimeout(() => {
        if (!ready && sequence === loadSequence) showPreviewUnavailable();
    }, 10000);

    player = new YT.Player("ytPlayerContainer", {
        videoId,
        playerVars: {
            autoplay: 0,
            modestbranding: 1,
            rel: 0,
        },
        events: {
            onReady: () => {
                if (sequence !== loadSequence) return;
                ready = true;
                clearTimeout(timeout);
                setStartBtn.disabled = false;
                setEndBtn.disabled = false;
                previewNotice.hidden = true;
                pollTimer = setInterval(() => {
                    if (player && typeof player.getCurrentTime === "function") {
                        updatePlayhead(player.getCurrentTime());
                    }
                }, 250);
            },
            onError: () => {
                if (sequence !== loadSequence) return;
                ready = true;
                clearTimeout(timeout);
                if (pollTimer) clearInterval(pollTimer);
                pollTimer = null;
                showPreviewUnavailable();
            },
        },
    });
}

function getCurrentTime() {
    return player?.getCurrentTime() ?? 0;
}

function seekTo(time) {
    player?.seekTo(time, true);
}

function initControls(videoDuration) {
    duration = videoDuration;
    startTime = 0;
    endTime = videoDuration;
    viewStart = 0;
    viewEnd = videoDuration;
    startInput.value = formatTime(0);
    endInput.value = formatTime(videoDuration);

    if (!controlsInitialized) {
        setupControlEvents();
        controlsInitialized = true;
    }
    updateAll();
}

function setupControlEvents() {
    $("ytSetStartBtn").addEventListener("click", () => {
        startTime = clamp(getCurrentTime(), 0, endTime - 0.1);
        startInput.value = formatTime(startTime);
        updateAll();
    });

    $("ytSetEndBtn").addEventListener("click", () => {
        endTime = clamp(getCurrentTime(), startTime + 0.1, duration);
        endInput.value = formatTime(endTime);
        updateAll();
    });

    startInput.addEventListener("change", () => {
        const value = parseTime(startInput.value);
        if (value !== null) {
            startTime = clamp(value, 0, endTime - 0.1);
            startInput.value = formatTime(startTime);
            updateAll();
        }
    });

    endInput.addEventListener("change", () => {
        const value = parseTime(endInput.value);
        if (value !== null) {
            endTime = clamp(value, startTime + 0.1, duration);
            endInput.value = formatTime(endTime);
            updateAll();
        }
    });

    handleStart.addEventListener("mousedown", (event) => {
        event.preventDefault();
        event.stopPropagation();
        dragMode = "start-handle";
        dragStartX = event.clientX;
        dragStartValue = startTime;
    });

    handleEnd.addEventListener("mousedown", (event) => {
        event.preventDefault();
        event.stopPropagation();
        dragMode = "end-handle";
        dragStartX = event.clientX;
        dragStartValue = endTime;
    });

    timeline.addEventListener("mousedown", (event) => {
        if (dragMode) return;
        const target = event.target;
        if (
            target === handleStart ||
            target === handleEnd ||
            target.closest("#ytHandleStart") ||
            target.closest("#ytHandleEnd")
        ) {
            return;
        }

        dragMode = "pan-timeline";
        dragStartX = event.clientX;
        dragStartValue = viewStart;
        dragStartValue2 = viewEnd;
    });

    overview.addEventListener("mousedown", (event) => {
        event.preventDefault();
        const rect = overview.getBoundingClientRect();
        const relX = event.clientX - rect.left;
        const viewportLeft = (viewStart / duration) * rect.width;
        const viewportRight = (viewEnd / duration) * rect.width;

        if (relX >= viewportLeft && relX <= viewportRight) {
            dragMode = "pan-overview";
            dragStartX = event.clientX;
            dragStartValue = viewStart;
        } else {
            const clickTime = (relX / rect.width) * duration;
            const viewDuration = viewEnd - viewStart;
            let newStart = clickTime - viewDuration / 2;
            let newEnd = clickTime + viewDuration / 2;
            if (newStart < 0) {
                newStart = 0;
                newEnd = viewDuration;
            }
            if (newEnd > duration) {
                newEnd = duration;
                newStart = duration - viewDuration;
            }
            viewStart = newStart;
            viewEnd = newEnd;
            updateAll();
        }
    });

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);

    timeline.addEventListener("wheel", (event) => {
        event.preventDefault();
        const rect = timeline.getBoundingClientRect();
        const fraction = (event.clientX - rect.left) / rect.width;
        const viewDuration = viewEnd - viewStart;
        const centerTime = viewStart + fraction * viewDuration;
        const zoomFactor = event.deltaY > 0 ? 1.3 : 1 / 1.3;
        zoomAt(centerTime, zoomFactor);
    }, { passive: false });

    $("ytZoomInBtn").addEventListener("click", () => zoomAt((viewStart + viewEnd) / 2, 0.5));
    $("ytZoomOutBtn").addEventListener("click", () => zoomAt((viewStart + viewEnd) / 2, 2));
    $("ytZoomFitBtn").addEventListener("click", () => {
        const selectedDuration = endTime - startTime;
        const padding = Math.max(selectedDuration * 0.3, 1);
        viewStart = Math.max(0, startTime - padding);
        viewEnd = Math.min(duration, endTime + padding);
        updateAll();
    });
}

function onMouseMove(event) {
    if (!dragMode) return;

    const dx = event.clientX - dragStartX;
    if (dragMode === "start-handle") {
        const rect = timeline.getBoundingClientRect();
        const dt = (dx / rect.width) * (viewEnd - viewStart);
        startTime = clamp(dragStartValue + dt, 0, endTime - 0.5);
        startInput.value = formatTime(startTime);
        updateAll();
    } else if (dragMode === "end-handle") {
        const rect = timeline.getBoundingClientRect();
        const dt = (dx / rect.width) * (viewEnd - viewStart);
        endTime = clamp(dragStartValue + dt, startTime + 0.5, duration);
        endInput.value = formatTime(endTime);
        updateAll();
    } else if (dragMode === "pan-timeline") {
        const rect = timeline.getBoundingClientRect();
        const viewDuration = viewEnd - viewStart;
        const dt = -(dx / rect.width) * viewDuration;
        let newStart = dragStartValue + dt;
        let newEnd = dragStartValue2 + dt;
        if (newStart < 0) {
            newEnd -= newStart;
            newStart = 0;
        }
        if (newEnd > duration) {
            newStart -= newEnd - duration;
            newEnd = duration;
        }
        viewStart = Math.max(0, newStart);
        viewEnd = Math.min(duration, newEnd);
        updateAll();
    } else if (dragMode === "pan-overview") {
        const rect = overview.getBoundingClientRect();
        const viewDuration = viewEnd - viewStart;
        const dt = (dx / rect.width) * duration;
        let newStart = dragStartValue + dt;
        let newEnd = newStart + viewDuration;
        if (newStart < 0) {
            newStart = 0;
            newEnd = viewDuration;
        }
        if (newEnd > duration) {
            newEnd = duration;
            newStart = duration - viewDuration;
        }
        viewStart = newStart;
        viewEnd = newEnd;
        updateAll();
    }
}

function onMouseUp(event) {
    if (dragMode === "pan-timeline" && Math.abs(event.clientX - dragStartX) < 3) {
        const rect = timeline.getBoundingClientRect();
        const fraction = (event.clientX - rect.left) / rect.width;
        seekTo(viewStart + fraction * (viewEnd - viewStart));
    }
    dragMode = null;
}

function zoomAt(centerTime, factor) {
    const viewDuration = viewEnd - viewStart;
    const minDuration = Math.min(MIN_VIEW_DURATION, duration);
    const newDuration = clamp(viewDuration * factor, minDuration, duration);
    const centerFraction = viewDuration > 0 ? (centerTime - viewStart) / viewDuration : 0.5;
    let newStart = centerTime - centerFraction * newDuration;
    let newEnd = centerTime + (1 - centerFraction) * newDuration;

    if (newStart < 0) {
        newEnd = Math.min(duration, newEnd - newStart);
        newStart = 0;
    }
    if (newEnd > duration) {
        newStart = Math.max(0, newStart - (newEnd - duration));
        newEnd = duration;
    }

    viewStart = newStart;
    viewEnd = newEnd;
    updateAll();
}

function updateAll() {
    updateOverview();
    updateTimeline();
    updateZoomLabel();
}

function updateOverview() {
    if (duration <= 0) return;
    overviewSelection.style.left = `${(startTime / duration) * 100}%`;
    overviewSelection.style.width = `${Math.max(0, ((endTime - startTime) / duration) * 100)}%`;
    overviewViewport.style.left = `${(viewStart / duration) * 100}%`;
    overviewViewport.style.width = `${Math.max(0, ((viewEnd - viewStart) / duration) * 100)}%`;
}

function updateTimeline() {
    const viewDuration = viewEnd - viewStart;
    if (viewDuration <= 0) return;

    selection.style.left = `${((startTime - viewStart) / viewDuration) * 100}%`;
    selection.style.width = `${((endTime - startTime) / viewDuration) * 100}%`;

    const startPct = ((startTime - viewStart) / viewDuration) * 100;
    const endPct = ((endTime - viewStart) / viewDuration) * 100;
    handleStart.style.left = `${startPct}%`;
    handleEnd.style.left = `${endPct}%`;
    handleStart.style.display = startTime >= viewStart && startTime <= viewEnd ? "" : "none";
    handleEnd.style.display = endTime >= viewStart && endTime <= viewEnd ? "" : "none";
}

function updateZoomLabel() {
    if (duration <= 0) return;
    const ratio = duration / (viewEnd - viewStart);
    zoomLevel.textContent = ratio <= 1.01 ? "" : `${ratio.toFixed(1)}x`;
}

function updatePlayhead(time) {
    if (duration <= 0) return;
    overviewPlayhead.style.left = `${(time / duration) * 100}%`;

    const viewDuration = viewEnd - viewStart;
    if (viewDuration <= 0) return;
    const pct = ((time - viewStart) / viewDuration) * 100;
    timelinePlayhead.style.left = `${clamp(pct, 0, 100)}%`;
    timelinePlayhead.style.display = time >= viewStart && time <= viewEnd ? "" : "none";
}

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

function pad(value) {
    return value.toString().padStart(2, "0");
}

function parseTime(value) {
    const parts = value.trim().split(":").map(Number);
    if (parts.some(Number.isNaN)) return null;
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return null;
}

const saveBtn = $("ytSaveBtn");
const saveFolder = $("ytSaveFolder");
const resultDownload = $("ytResultDownload");
const cancelBtn = $("ytCancelBtn");
const jobKey = "akatz-utils-clip-job";
let processing = false;
let activeJobId = null;

async function jsonRequest(url, options = {}) {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error ?? `Server error (${response.status})`);
    return body;
}

function setProcessing(value) {
    processing = value;
    downloadBtn.disabled = value;
    saveBtn.disabled = value;
    loadBtn.disabled = value;
    cancelBtn.hidden = !activeJobId;
}

async function followJob(id) {
    activeJobId = id;
    cancelBtn.disabled = false;
    setProcessing(true);
    resultDownload.hidden = true;
    try {
        while (true) {
            const job = await jsonRequest(`/api/ytclipper/jobs/${id}`);
            if (controlsSection.hidden && job.url) {
                currentUrl = job.url;
                urlInput.value = job.url;
                initControls(job.end);
                startTime = job.start;
                startInput.value = formatTime(startTime);
                updateAll();
                formatSelect.value = job.format;
                fastMP4.checked = !!job.copy_video;
                if (job.folder) saveFolder.value = job.folder;
                if (job.requested_filename) $("ytSaveFilename").value = job.requested_filename;
                setStartBtn.disabled = true;
                setEndBtn.disabled = true;
                controlsSection.hidden = false;
                previewNotice.textContent = "Clip settings restored. Load the video to show its preview and full timeline.";
                previewNotice.hidden = false;
            }
            if (["error", "cancelled", "complete"].includes(job.state)) {
                activeJobId = null;
                localStorage.removeItem(jobKey);
            }
            if (job.state === "error") throw new Error(job.error);
            if (job.state === "cancelled") {
                showStatus("Clip cancelled. Adjust options and start again.", "info");
                break;
            }
            if (job.state === "complete") {
                localStorage.removeItem(jobKey);
                resultDownload.href = job.download_url;
                resultDownload.hidden = false;
                if (job.destination === "shared") {
                    showStatus(`Saved to ${job.path} (${(job.bytes / 1024 / 1024).toFixed(1)} MB)`, "info");
                } else {
                    showStatus("Clip ready. Your browser download is starting; use the link below to download again.", "info");
                    resultDownload.click();
                }
                break;
            }
            if (job.cancel_requested) {
                cancelBtn.disabled = true;
                showStatus("Cancelling clip…", "info");
            } else {
                showStatus(`${job.phase ?? "Processing on the server"}… ${(job.bytes / 1024 / 1024).toFixed(1)} MB written. You can return to this page while it finishes.`, "info");
            }
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    } catch (error) {
        showStatus(`${error.message} Reload this page to reconnect to a running clip.`, "error");
    } finally {
        setProcessing(false);
    }
}

async function createClip(destination) {
    if (processing) return;
    setProcessing(true);
    resultDownload.hidden = true;
    showStatus("Starting clip on the server…", "info");
    try {
        const job = await jsonRequest("/api/ytclipper/jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({url: currentUrl, start: startTime, end: endTime,
                format: formatSelect.value, destination,
                copy_video: fastMP4.checked,
                folder: saveFolder.value.trim(), filename: $("ytSaveFilename").value.trim()}),
        });
        localStorage.setItem(jobKey, job.id);
        localStorage.setItem("akatz-utils-save-folder", saveFolder.value);
        await followJob(job.id);
    } catch (error) {
        showStatus(error.message, "error");
        setProcessing(false);
    }
}

async function browseFolders(path) {
    try {
        const data = await jsonRequest(`/api/ytclipper/folders?path=${encodeURIComponent(path)}`);
        saveFolder.value = data.path;
        const browser = $("ytFolderBrowser");
        browser.replaceChildren();
        browser.hidden = false;
        const entries = data.parent ? [{name: "↑ Parent folder", path: data.parent}, ...data.folders] : data.folders;
        for (const folder of entries) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-secondary";
            button.textContent = folder.name;
            button.addEventListener("click", () => browseFolders(folder.path));
            browser.appendChild(button);
        }
        if (!entries.length) browser.textContent = "No subfolders. You can use this folder or type a new folder path above.";
    } catch (error) {
        showStatus(error.message, "error");
    }
}

$("ytBrowseBtn").addEventListener("click", () => browseFolders(""));
saveBtn.addEventListener("click", () => createClip("shared"));
downloadBtn.addEventListener("click", () => createClip("browser"));
cancelBtn.addEventListener("click", async () => {
    if (!activeJobId) return;
    const id = activeJobId;
    cancelBtn.disabled = true;
    showStatus("Cancelling clip…", "info");
    try {
        await jsonRequest(`/api/ytclipper/jobs/${id}/cancel`, {method: "POST"});
        if (!processing) await followJob(id);
    } catch (error) {
        cancelBtn.disabled = false;
        showStatus(error.message, "error");
    }
});

(async () => {
    try {
        const storage = await jsonRequest("/api/ytclipper/storage");
        saveBtn.hidden = !storage.shared_enabled;
        $("ytSaveOptions").hidden = !storage.shared_enabled;
        saveFolder.value = localStorage.getItem("akatz-utils-save-folder") ?? storage.default_folder;
        const job = localStorage.getItem(jobKey);
        if (job) await followJob(job);
    } catch (error) {
        showStatus(error.message, "error");
    }
})();

loadBtn.addEventListener("click", async () => {
    const sequence = ++loadSequence;
    hideStatus();
    const url = urlInput.value.trim();
    if (!url) return;

    const videoId = extractVideoId(url);
    if (!videoId) {
        showStatus("Invalid YouTube URL", "error");
        return;
    }

    loadBtn.disabled = true;
    showStatus("Loading video...", "info");
    controlsSection.hidden = true;
    playerSection.hidden = true;

    try {
        const response = await fetch("/api/ytclipper/metadata", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });
        const metadata = await response.json();
        if (!response.ok) throw new Error(metadata.error ?? "Could not load video details");
        if (sequence !== loadSequence) return;

        currentUrl = url;
        initControls(metadata.duration);
        controlsSection.hidden = false;
        setStartBtn.disabled = true;
        setEndBtn.disabled = true;
        previewNotice.textContent = "Loading YouTube preview. You can still download the video.";
        previewNotice.hidden = false;
        hideStatus();
        loadBtn.disabled = false;

        await loadYouTubeAPI();
        if (sequence !== loadSequence) return;
        playerSection.hidden = false;
        loadVideo(videoId, sequence);
    } catch (error) {
        if (sequence !== loadSequence) return;
        if (!controlsSection.hidden) {
            showPreviewUnavailable();
            return;
        }
        showStatus(error instanceof Error ? error.message : String(error), "error");
        loadBtn.disabled = false;
    }
});

urlInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadBtn.click();
});
