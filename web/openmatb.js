// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// Browser launcher: loads Pyodide + pyglet in the background while the start menu
// is displayed, then runs main.py once the user clicks "Start" (a user gesture is
// required to enable audio and fullscreen).

import { installPygletEmscripten } from "./pyglet_emscripten.js";
import {
    SessionOutput, checkDataPipe, downloadText, gunzipIfNeeded, loadJatos, sessionOutputSettings, sessionRelativePath,
} from "./session_output.js";
import { connectScorm } from "./scorm.js";

// Set by web/build.py: pyodide.mjs on the Pyodide CDN, or its copy shipped with the page (--pyodide local)
const PYODIDE_MODULE = new URL(document.querySelector('meta[name="pyodide-module"]').content, location.href).href;
const APP_DIR = "/app";
const SESSIONS_DIR = "/data/openmatb/sessions"; // pyglet.storage.get("openmatb").data / "sessions"
let storage = null; // pyglet's storage bridge (persists /data in IndexedDB), set by boot()
const FONT_FAMILY = "Noto Sans"; // core.platform.WEB_FONT_NAME, files downloaded by web/build.py
const FONT_WEIGHTS = [400, 700];

const $ = (id) => document.getElementById(id);

// Start page texts (OpenMATB itself is translated with gettext, see locales/)
const TEXTS = {
    en_EN: {
        language: "Language",
        mode: "Mode",
        run_scenario: "Run a scenario",
        replay_session: "Replay a session",
        choose_next: "The scenario (or session) is chosen in the next screen.",
        import_session: "Import a session file (optional)",
        sessions_kept: "Sessions run in this browser are kept and listed automatically.",
        fullscreen: "Fullscreen",
        start: "Start",
        session_ended: "Session ended",
        log_file: "The log file",
        kept_in_browser: "It is also kept in this browser for replay.",
        sending: "Sending…",
        ending_study: "End of the study…",
        study_not_ended: "The study could not be ended in JATOS:",
        sent_download: "Downloaded on this computer",
        sent_fallback: "Downloaded on this computer, because it could not be sent",
        sent_webdav: "Sent to the server (WebDAV)",
        sent_jatos: "Sent to JATOS",
        sent_datapipe: "Sent to DataPipe",
        sent_scorm: "Activity completed in the learning platform (LMS)",
        sent_none: "Not sent anywhere (web_session_output=none)",
        demo_not_recorded: "This was a demo: the session was not recorded.",
        restart_demo: "Restart the demo",
        not_sent: "Not sent to {destination}:",
        config_error: "Configuration error (config.ini):",
        stored_sessions: "Sessions kept in this browser",
        no_session: "No session yet.",
        download: "Download",
        delete: "Delete",
        delete_all: "Delete all the sessions",
        confirm_delete: "Delete the session {name} from this browser?",
        confirm_delete_all: "Delete the {count} sessions kept in this browser?",
        back_to_menu: "Back to menu",
        joystick_hint: "Joystick: press one of its buttons to detect it.",
        joystick_detected: "Joystick detected:",
        loading_python: "Loading Python…",
        loading_pyglet: "Loading pyglet…",
        loading_openmatb: "Loading OpenMATB…",
        ready: "Ready",
        loading_failed: "Loading failed:",
        browser_warn: "The Firefox browser cannot guarantee the timing accuracy of the results, "
            + "prefer Chrome or Edge.",
        browser_block: "This experiment requires Chrome or Edge: Firefox pauses for 0.1 to 1 s every few seconds, "
            + "which makes timing unreliable.",
    },
    fr_FR: {
        language: "Langue",
        mode: "Mode",
        run_scenario: "Lancer un scénario",
        replay_session: "Rejouer une session",
        choose_next: "Le scénario (ou la session) est choisi à l'écran suivant.",
        import_session: "Importer un fichier de session (facultatif)",
        sessions_kept: "Les sessions lancées dans ce navigateur sont conservées et listées automatiquement.",
        fullscreen: "Plein écran",
        start: "Démarrer",
        session_ended: "Session terminée",
        log_file: "Le fichier de log",
        kept_in_browser: "Il est aussi conservé dans ce navigateur pour le rejouer.",
        sending: "Envoi en cours…",
        ending_study: "Fin de l'étude…",
        study_not_ended: "L'étude n'a pas pu être terminée dans JATOS :",
        sent_download: "Téléchargé sur cet ordinateur",
        sent_fallback: "Téléchargé sur cet ordinateur, car il n'a pas pu être envoyé",
        sent_webdav: "Envoyé au serveur (WebDAV)",
        sent_jatos: "Envoyé à JATOS",
        sent_datapipe: "Envoyé à DataPipe",
        sent_scorm: "Activité terminée dans la plateforme de formation (LMS)",
        sent_none: "Envoyé nulle part (web_session_output=none)",
        demo_not_recorded: "C'était une démonstration : la session n'a pas été enregistrée.",
        restart_demo: "Relancer la démo",
        not_sent: "Non envoyé à {destination} :",
        config_error: "Erreur de configuration (config.ini) :",
        stored_sessions: "Sessions conservées dans ce navigateur",
        no_session: "Aucune session pour le moment.",
        download: "Télécharger",
        delete: "Supprimer",
        delete_all: "Supprimer toutes les sessions",
        confirm_delete: "Supprimer la session {name} de ce navigateur ?",
        confirm_delete_all: "Supprimer les {count} sessions conservées dans ce navigateur ?",
        back_to_menu: "Retour au menu",
        joystick_hint: "Joystick : appuyez sur l'un de ses boutons pour le détecter.",
        joystick_detected: "Joystick détecté :",
        loading_python: "Chargement de Python…",
        loading_pyglet: "Chargement de pyglet…",
        loading_openmatb: "Chargement d'OpenMATB…",
        ready: "Prêt",
        loading_failed: "Échec du chargement :",
        browser_warn: "Le navigateur Firefox ne peut garantir la précision temporelle des résultats, "
            + "privilégiez Chrome ou Edge.",
        browser_block: "Cette expérience nécessite Chrome ou Edge : Firefox s'interrompt 0,1 à 1 s toutes les "
            + "quelques secondes, ce qui rend la mesure du temps peu fiable.",
    },
};

// ?lang= in the URL, otherwise the first browser language OpenMATB is translated in, otherwise English
function detectLanguage() {
    const requested = new URLSearchParams(location.search).get("lang");
    if (requested in TEXTS) {
        return requested;
    }
    for (const language of navigator.languages || [navigator.language]) {
        const code = String(language).toLowerCase().split("-")[0];
        const match = Object.keys(TEXTS).find((lang) => lang.toLowerCase().startsWith(code + "_"));
        if (match) {
            return match;
        }
    }
    return "en_EN";
}

const t = (key) => TEXTS[$("lang").value][key];

let statusKey = null;
const status = (key, detail = "") => {
    statusKey = key;
    $("pygletStatus").textContent = key ? `${t(key)} ${detail}`.trim() : detail;
};

function translatePage() {
    const lang = $("lang").value;
    document.documentElement.lang = lang.split("_")[0];
    for (const element of document.querySelectorAll("[data-i18n]")) {
        element.textContent = TEXTS[lang][element.dataset.i18n];
    }
    if (statusKey) {
        status(statusKey);
    }
}

// Browsers reveal a joystick only after one of its buttons is pressed (core/joystick.py reads it)
function showJoystick() {
    const gamepad = [...(navigator.getGamepads ? navigator.getGamepads() : [])].find((g) => g && g.connected);
    $("joystick-status").dataset.i18n = gamepad ? "joystick_detected" : "joystick_hint";
    $("joystick-status").textContent = t($("joystick-status").dataset.i18n);
    $("joystick-name").textContent = gamepad ? gamepad.id : "";
}
window.addEventListener("gamepadconnected", showJoystick);
window.addEventListener("gamepaddisconnected", showJoystick);

$("lang").value = detectLanguage();
translatePage();
$("lang").addEventListener("change", translatePage);
showJoystick();

// Browsers with known timing issues. Firefox pauses the page for 0.1 to 1 s every few seconds (garbage
// collection when the user is considered inactive, and others): measured by tests/web, see the README.
const TIMING_ISSUE_BROWSERS = [/Firefox\/|FxiOS\//];
const BROWSER_CHECK_MODES = ["warn", "block", "off"];

// ?browsercheck= in the URL, otherwise web_browser_check in config.ini (once OpenMATB is loaded), otherwise "warn"
function browserCheckMode(pyodide = null) {
    const requested = new URLSearchParams(location.search).get("browsercheck");
    if (BROWSER_CHECK_MODES.includes(requested)) {
        return requested;
    }
    try {
        const config = pyodide?.FS.readFile(`${APP_DIR}/config.ini`, { encoding: "utf8" }) ?? "";
        const mode = (config.match(/^\s*web_browser_check\s*=\s*(\w+)/m) || [])[1]?.toLowerCase();
        if (BROWSER_CHECK_MODES.includes(mode)) {
            return mode;
        }
    } catch (error) {
        console.warn("config.ini not readable:", error);
    }
    return "warn";
}

// Show (or hide) the notice for browsers with timing issues. Returns false when starting is not allowed.
// Called when the page opens, then again once config.ini is available (it is in app.zip).
function checkBrowser(pyodide = null) {
    const mode = browserCheckMode(pyodide);
    const concerned = mode !== "off" && TIMING_ISSUE_BROWSERS.some((pattern) => pattern.test(navigator.userAgent));
    $("browser-warning").hidden = !concerned;
    if (!concerned) {
        return true;
    }
    $("browser-warning").dataset.i18n = `browser_${mode}`;
    $("browser-warning").textContent = t(`browser_${mode}`);
    return mode !== "block";
}
checkBrowser();

// ?demo=1 (Demo tab of the website): runs the demo scenario, and nothing is recorded
const DEMO = new URLSearchParams(location.search).get("demo") === "1";
const DEMO_SCENARIO = "demo.txt";
// config.ini values of the demo: no session number to acknowledge, and the session is not sent anywhere
const DEMO_CONFIG = { display_session_number: "False", web_session_output: "none" };

function applyDemoConfig(pyodide) {
    let config = readAppConfig(pyodide);
    for (const [key, value] of Object.entries(DEMO_CONFIG)) {
        config = config.replace(new RegExp(`^(\\s*${key}\\s*=).*$`, "m"), `$1${value}`);
    }
    pyodide.FS.writeFile(`${APP_DIR}/config.ini`, config);
}
if (DEMO) {
    $("mode").value = "scenario";
    $("mode").hidden = true;
    document.querySelector('label[for="mode"]').hidden = true;
    $("back").dataset.i18n = "restart_demo";
    $("back").textContent = t("restart_demo");
}

// Run by an LMS (SCORM package): the LMS records the completion, participants only run the scenario
const scorm = connectScorm();
if (scorm) {
    $("mode").value = "scenario";
    $("mode").hidden = true;
    document.querySelector('label[for="mode"]').hidden = true;
    $("back").hidden = true; // The LMS takes over at the end
    window.addEventListener("pagehide", () => scorm.terminate());
}

async function loadFonts() {
    // pyglet measures and renders text with the fonts known by the document
    for (const weight of FONT_WEIGHTS) {
        const face = new FontFace(FONT_FAMILY, `url(fonts/noto-sans-${weight}.woff2)`, { weight: String(weight) });
        document.fonts.add(await face.load());
    }
}

async function boot() {
    status("loading_python");
    await loadFonts();
    const { loadPyodide } = await import(PYODIDE_MODULE);
    const pyodide = await loadPyodide();
    // Mounts /data (IndexedDB, where sessions are kept). The /cache mount (OPFS) is optional: Safari refuses
    // OPFS in private browsing, which made the loading fail. OpenMATB does not use it: keep /cache in memory then.
    const bridge = await installPygletEmscripten(pyodide, { cachePath: null });
    try {
        await bridge.mount_opfs("/cache");
    } catch (error) {
        console.warn("OPFS unavailable, /cache kept in memory:", error);
        pyodide.FS.mkdirTree("/cache");
    }

    status("loading_pyglet");
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    const wheels = (await (await fetch("wheels.txt")).text()).trim().split("\n");
    for (const wheel of wheels) {
        await micropip.install(new URL(`wheels/${wheel}`, location.href).href);
    }

    status("loading_openmatb");
    const app = await (await fetch("app.zip")).arrayBuffer();
    pyodide.unpackArchive(app, "zip", { extractDir: APP_DIR });
    if (DEMO) {
        applyDemoConfig(pyodide);
    }
    pyodide.runPython(`import os, sys; os.chdir("${APP_DIR}"); sys.path.insert(0, "${APP_DIR}")`);

    window.openmatb = { pyodide }; // for debugging from the browser console
    storage = bridge;
    status("ready");
    const outputErrors = sessionOutputSettings(readAppConfig(pyodide)).errors;
    $("start").disabled = !checkBrowser(pyodide) || !showConfigErrors(outputErrors);
    return pyodide;
}

function readAppConfig(pyodide) {
    try {
        return pyodide.FS.readFile(`${APP_DIR}/config.ini`, { encoding: "utf8" });
    } catch {
        return "";
    }
}

// Show the configuration errors (session destinations) on the start page. Returns false if there are some.
function showConfigErrors(errors) {
    $("config-error").hidden = errors.length === 0;
    $("config-error").textContent = errors.length ? `${t("config_error")} ${errors.join(" ; ")}` : "";
    return errors.length === 0;
}

// Session file destinations (web_session_output in config.ini), set when a scenario is started
let sessionOutput = null;
const DESTINATION_NAMES = {
    download: "download", webdav: "WebDAV", jatos: "JATOS", datapipe: "DataPipe", scorm: "LMS",
};

async function importSession(pyodide, file, bytes) {
    // Imported CSV files are stored with the browser sessions, so they appear in the replay selector.
    // Compressed files (.csv.gz, as sent to JATOS) are stored decompressed.
    const folder = `${SESSIONS_DIR}/imported`;
    pyodide.FS.mkdirTree(folder);
    const csv = await gunzipIfNeeded(bytes);
    pyodide.FS.writeFile(`${folder}/${file.name.replace(/\.gz$/i, "")}`, new Uint8Array(csv));
}

const ready = boot().catch((error) => {
    status("loading_failed", String(error));
    throw error;
});

// OpenMATB uses function keys (F1-F6 in sysmon...): don't let the browser reload the page,
// open its help or move the focus. preventDefault() still lets pyglet receive the key.
window.addEventListener("keydown", (event) => {
    if (!$("pygletCanvas").hidden && /^F([1-9]|1[0-2])$/.test(event.key) && event.key !== "F11") {
        event.preventDefault();
    }
}, { capture: true });

// ---- Sessions kept in this browser (replay mode): download them again or delete them ----

// Session files under SESSIONS_DIR (run in this browser, or imported), the most recent first
function storedSessions(pyodide) {
    const sessions = [];
    const walk = (folder) => {
        let names;
        try {
            names = pyodide.FS.readdir(folder);
        } catch {
            return; // No session yet
        }
        for (const name of names.filter((n) => n !== "." && n !== "..")) {
            const path = `${folder}/${name}`;
            const stat = pyodide.FS.stat(path);
            if (pyodide.FS.isDir(stat.mode)) {
                walk(path);
            } else if (name.endsWith(".csv")) {
                const time = new Date(stat.mtime).getTime();
                sessions.push({ path, name, folder: folder.slice(SESSIONS_DIR.length + 1), size: stat.size, time });
            }
        }
    };
    walk(SESSIONS_DIR);
    return sessions.sort((a, b) => b.time - a.time);
}

function sessionButton(label, icon, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.textContent = icon;
    button.addEventListener("click", action);
    return button;
}

async function deleteSessions(pyodide, sessions) {
    for (const session of sessions) {
        pyodide.FS.unlink(session.path);
    }
    await storage.sync_idbfs(); // Also delete them from the browser storage
    showStoredSessions();
}

async function showStoredSessions() {
    if ($("mode").value !== "replay") {
        return;
    }
    const pyodide = await ready;
    const sessions = storedSessions(pyodide);
    $("sessions-empty").hidden = sessions.length > 0;
    $("delete-all").hidden = sessions.length === 0;
    $("sessions-list").replaceChildren(...sessions.map((session) => {
        const row = document.createElement("li");
        const label = document.createElement("span");
        label.className = "session-name";
        label.textContent = session.name;
        const details = document.createElement("small");
        const size = `${Math.max(1, Math.round(session.size / 1024))} kB`;
        details.textContent = session.folder ? `${session.folder} · ${size}` : size;
        label.append(details);
        row.append(
            label,
            sessionButton(t("download"), "⬇️", () => {
                downloadText(session.name, pyodide.FS.readFile(session.path, { encoding: "utf8" }));
            }),
            sessionButton(t("delete"), "🗑️", () => {
                if (window.confirm(t("confirm_delete").replace("{name}", session.name))) {
                    deleteSessions(pyodide, [session]);
                }
            }),
        );
        return row;
    }));
    $("delete-all").onclick = () => {
        if (window.confirm(t("confirm_delete_all").replace("{count}", sessions.length))) {
            deleteSessions(pyodide, sessions);
        }
    };
}

$("mode").addEventListener("change", () => {
    $("replay-options").hidden = $("mode").value !== "replay";
    showStoredSessions();
});

$("start").addEventListener("click", async () => {
    // Everything that needs the user gesture must happen before the first await
    const wantsFullscreen = $("fullscreen").checked;
    const fullscreen = wantsFullscreen ? document.documentElement.requestFullscreen().catch(() => {}) : null;

    const params = new URLSearchParams(location.search);
    params.set("lang", $("lang").value);
    params.set("mode", $("mode").value);
    if (DEMO && !params.has("scenario")) {
        params.set("scenario", DEMO_SCENARIO);
    }
    history.replaceState(null, "", `?${params}`);

    const file = $("mode").value === "replay" ? $("session-file").files[0] : undefined;
    const bytes = file ? await file.arrayBuffer() : null;
    const pyodide = await ready;

    // Where the session file will go. config.ini is read again: it may have been changed since the loading
    if ($("mode").value !== "replay") {
        const settings = sessionOutputSettings(readAppConfig(pyodide));
        let jatos;
        try {
            if (settings.destinations.includes("jatos")) {
                jatos = await loadJatos();
            }
        } catch (error) {
            settings.errors.push(String(error.message || error));
        }
        // Better now than after the session: DataPipe must accept the files of the experiment (the demo sends nothing)
        if (settings.destinations.includes("datapipe") && !settings.errors.length && !DEMO) {
            try {
                await checkDataPipe(settings.datapipeExperiment);
            } catch (error) {
                settings.errors.push(String(error.message || error));
            }
        }
        if (!showConfigErrors(settings.errors)) {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            }
            return;
        }
        sessionOutput = new SessionOutput(settings, { jatos });
    }

    $("menu").hidden = true;
    $("pygletCanvas").hidden = false;
    await fullscreen;

    if (file) {
        await importSession(pyodide, file, bytes);
    }
    status(null);
    try {
        await pyodide.runPythonAsync(`import runpy; runpy.run_path("main.py", run_name="__main__")`);
        $("pygletCanvas").focus();
    } catch (error) {
        status(null, String(error));
        console.error(error);
    }
});

// Back to the menu, keeping the chosen language
const backToMenu = () => {
    location.href = `${location.pathname}?lang=${$("lang").value}${DEMO ? "&demo=1" : ""}`;
};
$("back").addEventListener("click", backToMenu);

// Dispatched when OpenMATB closes (end of scenario, replay closed or selection cancelled)
document.addEventListener("openmatb-exit", () => {
    if ($("end").hidden) {
        backToMenu();
    }
});

const readSessionFile = (pyodide, path) => pyodide.FS.readFile(path, { encoding: "utf8" });

// Dispatched by core.logger.Logger.checkpoint() every 10 s: send the file written so far (if configured)
document.addEventListener("openmatb-checkpoint", async (event) => {
    if (sessionOutput) {
        const pyodide = await ready;
        sessionOutput.checkpoint(sessionRelativePath(event.detail), readSessionFile(pyodide, event.detail));
    }
});

function destinationItem(text, ok) {
    const item = document.createElement("li");
    item.className = ok === undefined ? "" : ok ? "ok" : "failed";
    item.textContent = text;
    return item;
}

// Dispatched by core.logger.Logger.end_session(), with the path of the session file: download it and/or send it
document.addEventListener("openmatb-end", async (event) => {
    if (document.fullscreenElement) {
        document.exitFullscreen();
    }
    $("pygletCanvas").hidden = true;
    const relativePath = sessionRelativePath(event.detail);
    $("end-file").textContent = relativePath.split("/").pop();
    $("end-destinations").replaceChildren(destinationItem(t("sending")));
    // JATOS (like an LMS) takes over at the end: going back to the menu would reload the page and leave the study
    // run unfinished
    const inJatos = Boolean(sessionOutput?.settings.destinations.includes("jatos"));
    $("back").hidden = inJatos || Boolean(scorm);
    $("end").hidden = false;

    const pyodide = await ready;
    if (DEMO) {
        // Not kept for replay either
        pyodide.FS.unlink(event.detail);
        await storage.sync_idbfs();
        $("end-destinations").replaceChildren(destinationItem(t("demo_not_recorded")));
        document.querySelector('#end [data-i18n="kept_in_browser"]').hidden = true;
        return;
    }
    const output = sessionOutput || new SessionOutput(sessionOutputSettings(""));
    const results = await output.finish(relativePath, readSessionFile(pyodide, event.detail));
    if (scorm) {
        const ok = scorm.complete(relativePath);
        results.push(ok ? { destination: "scorm", ok } : { destination: "scorm", ok, error: "see the console" });
    }
    $("end-destinations").replaceChildren(...results.map((result) => destinationItem(
        result.ok
            ? t(`sent_${result.destination}`)
            : `${t("not_sent").replace("{destination}", DESTINATION_NAMES[result.destination])} ${result.error}`,
        result.ok,
    )));
    // JATOS: end the study run (JATOS end page, or the redirection set in JATOS, e.g. to Prolific)
    if (results.some((result) => result.destination === "jatos" && result.ok)) {
        $("end-destinations").append(destinationItem(t("ending_study")));
        await new Promise((resolve) => setTimeout(resolve, 1000)); // Time to read that the file was sent
        try {
            console.info("[OpenMATB] JATOS: ending the study run");
            await window.jatos.endStudy();
            return; // JATOS shows its end page
        } catch (error) {
            console.error("[OpenMATB] JATOS: the study run could not be ended:", error);
            $("end-destinations").lastChild.replaceWith(destinationItem(
                `${t("study_not_ended")} ${error?.message || error?.responseText || error}`, false,
            ));
        }
    }
    $("back").hidden = Boolean(scorm); // JATOS did not take over
});
