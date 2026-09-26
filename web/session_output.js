// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// Where the session files go (web_session_output in config.ini): downloaded on the participant's computer
// (default) and/or sent to a server: JATOS, DataPipe (OSF) or a WebDAV folder, or nowhere ("none"). The file is
// always kept in the browser storage too (replay). core/logger.py tells the page when the file changes ("openmatb-checkpoint",
// every 10 s) and when the session ends ("openmatb-end"), with the path of the file in the Pyodide file system.

export const DESTINATIONS = ["download", "jatos", "datapipe", "webdav", "none"];
export const DATAPIPE_URL = "https://pipe.jspsych.org/api/data/";
const SESSIONS_FOLDER = "/sessions/"; // Path of the session files: .../sessions/<YYYY-MM-DD>/<file>.csv

// Value of a key of config.ini ([Openmatb] section, "key=value" lines), or null
export function readConfigValue(configText, key) {
    const match = configText.match(new RegExp(`^\\s*${key}\\s*=(.*)$`, "m"));
    return match ? match[1].trim() : null;
}

// Settings from config.ini. errors: configuration problems to show on the start page
export function sessionOutputSettings(configText) {
    const errors = [];
    const requested = (readConfigValue(configText, "web_session_output") || "download")
        .split(",").map((d) => d.trim().toLowerCase()).filter((d) => d);
    const destinations = [];
    for (const destination of requested) {
        if (!DESTINATIONS.includes(destination)) {
            errors.push(`web_session_output: unknown destination "${destination}" (${DESTINATIONS.join(", ")})`);
        } else if (!destinations.includes(destination)) {
            destinations.push(destination);
        }
    }
    const settings = {
        destinations: destinations.length ? destinations : ["download"],
        datapipeExperiment: readConfigValue(configText, "web_datapipe_experiment") || "",
        webdavUrl: readConfigValue(configText, "web_webdav_url") || "",
        errors,
    };
    if (settings.destinations.includes("datapipe") && !settings.datapipeExperiment) {
        errors.push("web_datapipe_experiment is required to send the sessions to DataPipe");
    }
    if (settings.destinations.includes("webdav") && !settings.webdavUrl) {
        errors.push("web_webdav_url is required to send the sessions to a WebDAV folder");
    }
    return settings;
}

// "2026-09-26/12_260926_101500.csv" from the path of a session file
export function sessionRelativePath(path) {
    const index = path.lastIndexOf(SESSIONS_FOLDER);
    return index >= 0 ? path.slice(index + SESSIONS_FOLDER.length) : path.split("/").pop();
}

export function downloadText(filename, text, mime = "text/csv") {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

// gzip compression of a text or a Blob (CompressionStream: Chrome 80, Firefox 113, Safari 16.4)
export async function gzip(text) {
    const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
    return new Blob([await new Response(stream).arrayBuffer()], { type: "application/gzip" });
}

// Bytes (ArrayBuffer) decompressed if they are gzip data, unchanged otherwise
export async function gunzipIfNeeded(bytes) {
    const header = new Uint8Array(bytes, 0, Math.min(2, bytes.byteLength));
    if (header[0] !== 0x1f || header[1] !== 0x8b) {
        return bytes;
    }
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).arrayBuffer();
}

// Scenario time of the last row of a session file (second column), without splitting the whole file
function lastScenarioTime(csv) {
    const text = csv.trimEnd();
    const time = Number(text.slice(text.lastIndexOf("\n") + 1).split(",")[1]);
    return Number.isFinite(time) ? time : null;
}

async function describeError(response) {
    let detail = "";
    try {
        const body = await response.json();
        detail = body.message || body.error || "";
    } catch {
        // Not a JSON response
    }
    return `HTTP ${response.status}${detail ? ` (${detail})` : ""}`;
}

// ---- Destinations: checkpoint(relativePath, csv) during the session, finish(relativePath, csv) at the end ----

// Only kept in the browser storage
class Nowhere {
    async finish() {}
}

class Download {
    async finish(relativePath, csv) {
        downloadText(relativePath.split("/").pop(), csv);
    }
}

class WebDAV {
    constructor(url, fetchImpl) {
        this.url = url.endsWith("/") ? url : `${url}/`;
        this.fetch = fetchImpl;
        this.folderCreated = false;
        this.uploadedPath = null; // Name used on the server (another browser may have sent the same one)
    }

    async put(relativePath, csv) {
        const [folder, filename] = relativePath.includes("/") ? relativePath.split("/") : ["", relativePath];
        if (folder && !this.folderCreated) {
            // The day folder may already exist (405) or be created by the server (nginx create_full_put_path)
            await this.fetch(`${this.url}${folder}/`, { method: "MKCOL" });
            this.folderCreated = true;
        }
        if (this.uploadedPath) {
            await this.send(this.uploadedPath, csv, false);
            return;
        }
        // First upload: never overwrite a file sent by someone else (same session number, same second)
        const [stem, extension] = [filename.replace(/\.csv$/, ""), ".csv"];
        for (let n = 1; n <= 20; n++) {
            const candidate = `${folder ? `${folder}/` : ""}${stem}${n > 1 ? `_${n}` : ""}${extension}`;
            if (await this.send(candidate, csv, true)) {
                this.uploadedPath = candidate;
                return;
            }
        }
        throw new Error("no free file name on the server");
    }

    // Returns false when the file already exists (only when onlyIfNew)
    async send(path, csv, onlyIfNew) {
        const headers = { "Content-Type": "text/csv; charset=utf-8" };
        if (onlyIfNew) {
            headers["If-None-Match"] = "*";
        }
        const response = await this.fetch(`${this.url}${path}`, { method: "PUT", headers, body: csv });
        if (onlyIfNew && response.status === 412) {
            return false;
        }
        if (!response.ok) {
            throw new Error(await describeError(response));
        }
        return true;
    }

    checkpoint(relativePath, csv) {
        return this.put(relativePath, csv);
    }

    finish(relativePath, csv) {
        return this.put(relativePath, csv);
    }
}

// jatos.js rejects with an Error, a message or a request object, depending on the call and the JATOS version
function jatosError(error) {
    if (error instanceof Error) {
        return error;
    }
    const detail = error?.responseText || error?.statusText || error?.message || String(error);
    return new Error(error?.status ? `HTTP ${error.status} (${detail})` : detail);
}

// The session file is uploaded as a gzip result file: JATOS limits the result data to 5 MB by default (a session
// writes about 70 MB of CSV per hour) and the result files to 30 MB (about 14 MB per hour once compressed).
// It is uploaded again under the same name at every checkpoint, replacing the previous upload.
// The result data only holds a summary, shown in the JATOS result pages.
class JATOS {
    constructor(jatos) {
        this.jatos = jatos;
    }

    async send(relativePath, csv, state) {
        const filename = `${relativePath.split("/").pop()}.gz`;
        const raw = new Blob([csv]);
        const file = await gzip(raw);
        const summary = { file: filename, state, scenario_time: lastScenarioTime(csv), csv_bytes: raw.size };
        console.info(`[OpenMATB] JATOS: uploading ${filename} (${Math.round(file.size / 1024)} kB, ${state})`);
        try {
            await this.jatos.uploadResultFile(file, filename);
            await this.jatos.submitResultData(JSON.stringify(summary));
        } catch (error) {
            throw jatosError(error);
        }
        console.info(`[OpenMATB] JATOS: ${filename} uploaded`);
    }

    checkpoint(relativePath, csv) {
        return this.send(relativePath, csv, "running");
    }

    finish(relativePath, csv) {
        return this.send(relativePath, csv, "finished");
    }
}

class DataPipe {
    constructor(experimentID, fetchImpl) {
        this.experimentID = experimentID;
        this.fetch = fetchImpl;
    }

    // DataPipe rejects a file name that already exists: the file is only sent at the end
    async finish(relativePath, csv) {
        let filename = relativePath.split("/").pop();
        for (let attempt = 0; attempt < 2; attempt++) {
            const response = await this.fetch(DATAPIPE_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json", Accept: "*/*" },
                body: JSON.stringify({ experimentID: this.experimentID, filename, data: csv }),
            });
            if (response.ok) {
                return;
            }
            const body = await response.json().catch(() => ({}));
            if (body.error !== "FILE_EXISTS") {
                throw new Error(`HTTP ${response.status}${body.message || body.error ? ` (${body.message || body.error})` : ""}`);
            }
            filename = filename.replace(/\.csv$/, `_${Math.random().toString(36).slice(2, 8)}.csv`);
        }
        throw new Error("file name already used on DataPipe");
    }
}

export class SessionOutput {
    constructor(settings, { fetchImpl = (...args) => fetch(...args), jatos = window.jatos } = {}) {
        this.settings = settings;
        this.destinations = settings.destinations.map((name) => {
            switch (name) {
                case "webdav": return [name, new WebDAV(settings.webdavUrl, fetchImpl)];
                case "jatos": return [name, new JATOS(jatos)];
                case "datapipe": return [name, new DataPipe(settings.datapipeExperiment, fetchImpl)];
                case "none": return [name, new Nowhere()];
                default: return [name, new Download()];
            }
        });
        this.pending = new Map(); // Destination name -> checkpoint upload in progress
        this.finished = false;
    }

    // During the session: send the file written so far (skipped while the previous upload is in progress)
    checkpoint(relativePath, csv) {
        if (this.finished) {
            return;
        }
        for (const [name, destination] of this.destinations) {
            if (!destination.checkpoint || this.pending.has(name)) {
                continue;
            }
            const upload = Promise.resolve()
                .then(() => destination.checkpoint(relativePath, csv))
                .catch((error) => console.warn(`Session checkpoint not sent to ${name}:`, error))
                .finally(() => this.pending.delete(name));
            this.pending.set(name, upload);
        }
    }

    // End of the session: returns [{destination, ok, error}]. If the file could not be sent anywhere and was not
    // downloaded, it is downloaded anyway (destination "fallback").
    async finish(relativePath, csv) {
        this.finished = true;
        await Promise.all(this.pending.values()); // Keep the uploads in order
        const results = [];
        for (const [name, destination] of this.destinations) {
            try {
                await destination.finish(relativePath, csv);
                results.push({ destination: name, ok: true });
            } catch (error) {
                console.error(`[OpenMATB] Session file not sent to ${name}:`, error);
                results.push({ destination: name, ok: false, error: String(error.message || error) });
            }
        }
        if (!results.some((r) => r.ok)) {
            downloadText(relativePath.split("/").pop(), csv);
            results.push({ destination: "fallback", ok: true });
        }
        return results;
    }
}

// Load jatos.js (served by JATOS next to the study files) and wait until it is ready
export function loadJatos() {
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "jatos.js";
        script.onload = () => window.jatos.onLoad(() => resolve(window.jatos));
        script.onerror = () => reject(new Error("jatos.js not found: run the study from JATOS"));
        document.head.appendChild(script);
    });
}
