// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// Browser launcher: loads Pyodide + pyglet in the background while the start menu
// is displayed, then runs main.py once the user clicks "Start" (a user gesture is
// required to enable audio and fullscreen).

import { installPygletEmscripten } from "./pyglet_emscripten.js";

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
        log_downloaded: "has been downloaded. It is also kept in this browser for replay.",
        back_to_menu: "Back to menu",
        loading_python: "Loading Python…",
        loading_pyglet: "Loading pyglet…",
        loading_openmatb: "Loading OpenMATB…",
        ready: "Ready",
        loading_failed: "Loading failed:",
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
        log_downloaded: "a été téléchargé. Il est aussi conservé dans ce navigateur pour le rejouer.",
        back_to_menu: "Retour au menu",
        loading_python: "Chargement de Python…",
        loading_pyglet: "Chargement de pyglet…",
        loading_openmatb: "Chargement d'OpenMATB…",
        ready: "Prêt",
        loading_failed: "Échec du chargement :",
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

$("lang").value = detectLanguage();
translatePage();
$("lang").addEventListener("change", translatePage);

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
    await installPygletEmscripten(pyodide); // mounts /data (IndexedDB) and /cache

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
    $("start").disabled = false;
    return pyodide;
}

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

    $("menu").hidden = true;
    $("pygletCanvas").hidden = false;
    await fullscreen;

    const pyodide = await ready;
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

// Dispatched by core.logger.Logger.end_session() (the CSV download is triggered from Python)
document.addEventListener("openmatb-end", (event) => {
    if (document.fullscreenElement) {
        document.exitFullscreen();
    }
    $("pygletCanvas").hidden = true;
    $("end-file").textContent = event.detail;
    $("end").hidden = false;
});
