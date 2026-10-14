window.akatzExport = {
    folder() {
        return document.getElementById("sharedExportEnabled")?.checked
            ? document.getElementById("sharedExportFolder").value.trim() : null;
    },
    headers() {
        const folder = this.folder();
        return folder !== null ? {"X-Akatz-Save-Folder": folder || "Projects/Akatz-Utils/exports"} : {};
    },
    async saved(response) {
        if (this.folder() === null) return false;
        const result = await response.json();
        const status = document.getElementById("sharedExportStatus");
        status.textContent = response.ok ? `Saved to ${result.path}` : (result.error ?? "Save failed");
        return true;
    },
    async download(url) {
        if (this.folder() === null) {
            window.location.href = url;
            return;
        }
        const status = document.getElementById("sharedExportStatus");
        status.textContent = "Saving to shared drive…";
        try {
            const response = await fetch(url, {method: "POST", headers: this.headers()});
            await this.saved(response);
        } catch (error) {
            status.textContent = error.message;
        }
    },
};
