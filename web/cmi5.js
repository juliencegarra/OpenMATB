// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// cmi5 run-time, used when OpenMATB is imported into an LMS as a cmi5 package (python web/build.py --cmi5).
// cmi5 is the successor of SCORM: the LMS launches the page with the address of its Learning Record Store (LRS)
// and the page sends xAPI statements to it: initialized, completed (with the name of the session file), terminated.
// As with SCORM, the session file itself still goes where web_session_output in config.ini says.
// Specification: https://github.com/AICC/CMI-5_Spec_Current/blob/quartz/cmi5_spec.md

export const XAPI_VERSION = "1.0.3";
export const VERBS = {
    initialized: "http://adlnet.gov/expapi/verbs/initialized",
    completed: "http://adlnet.gov/expapi/verbs/completed",
    terminated: "http://adlnet.gov/expapi/verbs/terminated",
};
const CMI5_CATEGORY = "https://w3id.org/xapi/cmi5/context/categories/cmi5";
const MOVEON_CATEGORY = "https://w3id.org/xapi/cmi5/context/categories/moveon";
// Context extension of the "completed" statement: the name of the session file, to match each learner with it
export const SESSION_FILE_EXTENSION = "https://github.com/juliencegarra/OpenMATB/xapi/extensions/session-file";
const LAUNCH_PARAMETERS = ["endpoint", "fetch", "actor", "registration", "activityId"];

// The launch parameters of the page address, or null when the page was not launched by a cmi5 LMS
export function cmi5LaunchParameters(search = location.search) {
    const params = new URLSearchParams(search);
    if (!LAUNCH_PARAMETERS.every((name) => params.get(name))) {
        return null;
    }
    const launch = Object.fromEntries(LAUNCH_PARAMETERS.map((name) => [name, params.get(name)]));
    launch.actor = JSON.parse(launch.actor);
    launch.endpoint = launch.endpoint.endsWith("/") ? launch.endpoint : `${launch.endpoint}/`;
    return launch;
}

// ISO 8601 duration, as xAPI expects it (PT3725.5S)
export function isoDuration(seconds) {
    return `PT${Math.max(0, Math.round(seconds * 100) / 100)}S`;
}

// "fr-FR,en-US" (cmi5LearnerPreferences) -> "fr_FR", the first language OpenMATB is translated in, or null
export function preferredLanguage(languagePreference, languages) {
    for (const language of String(languagePreference || "").split(",")) {
        const [code, region] = language.trim().split("-");
        const exact = languages.find((lang) => lang.toLowerCase() === `${code}_${region || ""}`.toLowerCase());
        const sameCode = languages.find((lang) => lang.toLowerCase().startsWith(`${code.toLowerCase()}_`));
        if (exact || sameCode) {
            return exact || sameCode;
        }
    }
    return null;
}

export class Cmi5Session {
    constructor(launch, { fetchImpl = (...args) => fetch(...args), now = () => performance.now() } = {}) {
        this.launch = launch;
        this.fetch = fetchImpl;
        this.now = now;
        this.token = null;
        this.launchData = null;
        this.started = null;
        this.completed = false;
        this.terminated = false;
    }

    // Normal: the activity is recorded. Browse and Review: the LMS asks not to record a completion
    get launchMode() {
        return this.launchData?.launchMode || "Normal";
    }

    get returnURL() {
        return this.launchData?.returnURL || null;
    }

    headers(extra = {}) {
        return {
            Authorization: `Basic ${this.token}`,
            "X-Experience-API-Version": XAPI_VERSION,
            ...extra,
        };
    }

    // Documents of the LRS, by resource (activities/state, agents/profile) and query parameters
    async getDocument(resource, params) {
        const query = new URLSearchParams({ ...params, agent: JSON.stringify(this.launch.actor) });
        const response = await this.fetch(`${this.launch.endpoint}${resource}?${query}`, { headers: this.headers() });
        if (response.status === 404) {
            return null;
        }
        if (!response.ok) {
            throw new Error(`cmi5: ${resource} ${params.stateId || params.profileId}: HTTP ${response.status}`);
        }
        return response.json();
    }

    // When the page opens: the authorization token (the fetch URL works only once), the launch data, then the
    // "initialized" statement
    async initialize() {
        const response = await this.fetch(this.launch.fetch, { method: "POST" });
        const body = await response.json().catch(() => ({}));
        if (!response.ok || !body["auth-token"]) {
            const reason = body["error-text"] || `HTTP ${response.status}`;
            throw new Error(`cmi5: the LMS refused the launch (${reason}). Launch the activity again from the LMS.`);
        }
        this.token = body["auth-token"];
        this.launchData = await this.getDocument("activities/state", {
            stateId: "LMS.LaunchData",
            activityId: this.launch.activityId,
            registration: this.launch.registration,
        });
        if (!this.launchData) {
            throw new Error("cmi5: no launch data in the LRS");
        }
        this.started = this.now();
        await this.send("initialized");
    }

    // "fr-FR,en-US", or null
    async languagePreference() {
        try {
            const preferences = await this.getDocument("agents/profile", { profileId: "cmi5LearnerPreferences" });
            return preferences?.languagePreference || null;
        } catch (error) {
            console.warn(error);
            return null;
        }
    }

    statement(verb, { result, categories = [CMI5_CATEGORY], extensions } = {}) {
        const template = structuredClone(this.launchData.contextTemplate || {});
        const contextActivities = template.contextActivities || {};
        contextActivities.category = [...(contextActivities.category || []), ...categories.map((id) => ({ id }))];
        const context = {
            ...template,
            registration: this.launch.registration,
            contextActivities,
        };
        if (extensions) {
            context.extensions = { ...(template.extensions || {}), ...extensions };
        }
        return {
            id: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            actor: this.launch.actor,
            verb: { id: VERBS[verb], display: { "en-US": verb } },
            object: { id: this.launch.activityId, objectType: "Activity" },
            ...(result ? { result } : {}),
            context,
        };
    }

    async post(statement, { keepalive = false } = {}) {
        const response = await this.fetch(`${this.launch.endpoint}statements`, {
            method: "POST",
            headers: this.headers({ "Content-Type": "application/json" }),
            body: JSON.stringify(statement),
            keepalive,
        });
        if (!response.ok) {
            throw new Error(`cmi5: ${statement.verb.display["en-US"]} statement refused (HTTP ${response.status})`);
        }
    }

    send(verb, options = {}) {
        return this.post(this.statement(verb, options), options);
    }

    duration() {
        return isoDuration((this.now() - this.started) / 1000);
    }

    // End of a session: completed, with the name of the session file. Not in Browse or Review mode (cmi5 forbids it).
    // Returns false when nothing was recorded for this reason.
    async complete(sessionFile) {
        if (this.launchMode !== "Normal" || this.completed || this.terminated) {
            return false;
        }
        await this.send("completed", {
            result: { completion: true, duration: this.duration() },
            categories: [CMI5_CATEGORY, MOVEON_CATEGORY],
            extensions: { [SESSION_FILE_EXTENSION]: sessionFile },
        });
        this.completed = true;
        return true;
    }

    // The last statement: after it the LMS takes over. keepalive: sent while the page is closed
    async terminate({ keepalive = false } = {}) {
        if (this.terminated || !this.token) {
            return;
        }
        this.terminated = true;
        await this.send("terminated", { result: { duration: this.duration() }, keepalive });
    }
}

// The cmi5 session of the page (initialized), null when the page was not launched by a cmi5 LMS. Rejects when the
// LMS or its LRS refused the launch: nothing would be recorded.
export async function connectCmi5(options = {}) {
    const launch = cmi5LaunchParameters(options.search);
    if (!launch) {
        return null;
    }
    const session = new Cmi5Session(launch, options);
    await session.initialize();
    return session;
}
