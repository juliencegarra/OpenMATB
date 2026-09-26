// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// Browser launcher: loads Pyodide + pyglet in the background while the start menu
// is displayed, then runs main.py once the user clicks "Start" (a user gesture is
// required to enable audio and fullscreen).

import { installPygletEmscripten } from "./pyglet_emscripten.js";
import { SessionOutput, loadJatos, sessionOutputSettings, sessionRelativePath } from "./session_output.js";

const PYODIDE_VERSION = "0.29.4";
const APP_DIR = "/app";
const SESSIONS_DIR = "/data/openmatb/sessions"; // pyglet.storage.get("openmatb").data / "sessions"
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
        sent_download: "Downloaded on this computer",
        sent_fallback: "Downloaded on this computer, because it could not be sent",
        sent_webdav: "Sent to the server (WebDAV)",
        sent_jatos: "Sent to JATOS",
        sent_datapipe: "Sent to the OSF (DataPipe)",
        not_sent: "Not sent to {destination}:",
        config_error: "Configuration error (config.ini):",
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
        sent_download: "Téléchargé sur cet ordinateur",
        sent_fallback: "Téléchargé sur cet ordinateur, car il n'a pas pu être envoyé",
        sent_webdav: "Envoyé au serveur (WebDAV)",
        sent_jatos: "Envoyé à JATOS",
        sent_datapipe: "Envoyé à l'OSF (DataPipe)",
        not_sent: "Non envoyé à {destination} :",
        config_error: "Erreur de configuration (config.ini) :",
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
    const { loadPyodide } = await import(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.mjs`);
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
    pyodide.runPython(`import os, sys; os.chdir("${APP_DIR}"); sys.path.insert(0, "${APP_DIR}")`);

    window.openmatb = { pyodide }; // for debugging from the browser console
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
const DESTINATION_NAMES = { download: "download", webdav: "WebDAV", jatos: "JATOS", datapipe: "DataPipe" };

function importSession(pyodide, file, bytes) {
    // Imported CSV files are stored with the browser sessions, so they appear in the replay selector
    const folder = `${SESSIONS_DIR}/imported`;
    pyodide.FS.mkdirTree(folder);
    pyodide.FS.writeFile(`${folder}/${file.name}`, new Uint8Array(bytes));
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

$("mode").addEventListener("change", () => {
    $("replay-options").hidden = $("mode").value !== "replay";
});

$("start").addEventListener("click", async () => {
    // Everything that needs the user gesture must happen before the first await
    const wantsFullscreen = $("fullscreen").checked;
    const fullscreen = wantsFullscreen ? document.documentElement.requestFullscreen().catch(() => {}) : null;

    const params = new URLSearchParams(location.search);
    params.set("lang", $("lang").value);
    params.set("mode", $("mode").value);
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
        importSession(pyodide, file, bytes);
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
const backToMenu = () => { location.href = `${location.pathname}?lang=${$("lang").value}`; };
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
    $("end").hidden = false;

    const pyodide = await ready;
    const output = sessionOutput || new SessionOutput(sessionOutputSettings(""));
    const results = await output.finish(relativePath, readSessionFile(pyodide, event.detail));
    $("end-destinations").replaceChildren(...results.map((result) => destinationItem(
        result.ok
            ? t(`sent_${result.destination}`)
            : `${t("not_sent").replace("{destination}", DESTINATION_NAMES[result.destination])} ${result.error}`,
        result.ok,
    )));
    // JATOS: end the study run (JATOS end page, or the redirection set in JATOS, e.g. to Prolific)
    if (results.some((result) => result.destination === "jatos" && result.ok)) {
        setTimeout(() => window.jatos.endStudy(), 3000);
    }
});
