// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// SCORM run-time (1.2 and 2004), used when OpenMATB is imported into an LMS as a SCORM package
// (python web/build.py --scorm). The LMS only records that the activity was started / completed, the time spent
// and the name of the session file (lesson location): the session file itself is far too big for the LMS, it
// still goes where web_session_output in config.ini says (download, JATOS, DataPipe, WebDAV).

// The data model elements of each version
const VERSIONS = {
    "1.2": {
        name: "API",
        initialize: "LMSInitialize",
        terminate: "LMSFinish",
        getValue: "LMSGetValue",
        setValue: "LMSSetValue",
        commit: "LMSCommit",
        getLastError: "LMSGetLastError",
        status: "cmi.core.lesson_status",
        location: "cmi.core.lesson_location",
        learnerId: "cmi.core.student_id",
        sessionTime: "cmi.core.session_time",
        exit: "cmi.core.exit",
        sessionTimeFormat: (seconds) => {
            // HHHH:MM:SS.SS
            const pad = (n, width = 2) => String(n).padStart(width, "0");
            const centiseconds = Math.min(Math.round(seconds * 100), 9999 * 360000 - 1);
            const hours = Math.floor(centiseconds / 360000);
            const minutes = Math.floor((centiseconds % 360000) / 6000);
            return `${pad(hours, 4)}:${pad(minutes)}:${((centiseconds % 6000) / 100).toFixed(2).padStart(5, "0")}`;
        },
    },
    "2004": {
        name: "API_1484_11",
        initialize: "Initialize",
        terminate: "Terminate",
        getValue: "GetValue",
        setValue: "SetValue",
        commit: "Commit",
        getLastError: "GetLastError",
        status: "cmi.completion_status",
        location: "cmi.location",
        learnerId: "cmi.learner_id",
        sessionTime: "cmi.session_time",
        exit: "cmi.exit",
        sessionTimeFormat: (seconds) => `PT${seconds.toFixed(2)}S`, // ISO 8601 duration
    },
};

// Standard API discovery: the LMS puts the API object in a parent frame of the content, or in the window that
// opened it (content opened in a new window). Cross-origin frames can't be read: they are skipped.
export function findScormApi(win = window) {
    const lookUp = (start) => {
        let current = start;
        for (let depth = 0; current && depth < 500; depth++) {
            for (const version of ["2004", "1.2"]) {
                try {
                    const api = current[VERSIONS[version].name];
                    if (api && typeof api[VERSIONS[version].initialize] === "function") {
                        return { version, api };
                    }
                } catch {
                    // Cross-origin frame
                }
            }
            let parent = null;
            try {
                parent = current.parent;
            } catch {
                // Cross-origin frame
            }
            if (!parent || parent === current) {
                break;
            }
            current = parent;
        }
        return null;
    };
    let opener = null;
    try {
        opener = win.opener;
    } catch {
        // Cross-origin opener
    }
    return lookUp(win) || (opener ? lookUp(opener) : null);
}

export class ScormSession {
    // found: the result of findScormApi()
    constructor({ version, api }, now = () => performance.now()) {
        this.version = version;
        this.api = api;
        this.names = VERSIONS[version];
        this.now = now;
        this.started = now();
        this.active = false;
        this.completed = false;
    }

    call(method, ...args) {
        const result = String(this.api[this.names[method]](...args));
        if (result === "false") {
            const error = this.api[this.names.getLastError]();
            console.warn(`SCORM ${this.names[method]}(${args.join(", ")}) failed, error ${error}`);
        }
        return result;
    }

    get(element) {
        return this.call("getValue", this.names[element]);
    }

    set(element, value) {
        return this.call("setValue", this.names[element], String(value)) === "true";
    }

    // When the page opens. The activity stays "incomplete" until a session ends (a completed one stays completed)
    initialize() {
        this.active = this.call("initialize", "") === "true";
        if (!this.active) {
            return false;
        }
        const status = this.get("status");
        this.completed = status === "completed" || status === "passed";
        if (!this.completed) {
            this.set("status", "incomplete");
        }
        this.call("commit", "");
        return true;
    }

    learnerId() {
        return this.active ? this.get("learnerId") : "";
    }

    // End of a session: completed, with the name of the session file (to find it among the collected files)
    complete(sessionFile) {
        if (!this.active) {
            return false;
        }
        const ok = this.set("status", "completed") && this.set("location", sessionFile);
        this.call("commit", "");
        this.completed = this.completed || ok;
        return ok;
    }

    // When the page is closed: the time spent, then the LMS takes over
    terminate() {
        if (!this.active) {
            return;
        }
        this.active = false;
        this.set("sessionTime", this.names.sessionTimeFormat((this.now() - this.started) / 1000));
        this.set("exit", this.version === "2004" ? "normal" : "");
        this.call("commit", "");
        this.call("terminate", "");
    }
}

// The SCORM session of the page (initialized), or null when the page is not run by an LMS
export function connectScorm(win = window) {
    const found = findScormApi(win);
    if (!found) {
        return null;
    }
    const session = new ScormSession(found);
    return session.initialize() ? session : null;
}
