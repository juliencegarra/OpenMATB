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

const $ = (id) => document.getElementById(id);
const status = (text) => { $("pygletStatus").textContent = text; };

async function boot() {
    status("Loading Python…");
    const { loadPyodide } = await import(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.mjs`);
    const pyodide = await loadPyodide();
    await installPygletEmscripten(pyodide); // mounts /data (IndexedDB) and /cache

    status("Loading pyglet…");
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    const wheels = (await (await fetch("wheels.txt")).text()).trim().split("\n");
    for (const wheel of wheels) {
        await micropip.install(new URL(`wheels/${wheel}`, location.href).href);
    }

    status("Loading OpenMATB…");
    const app = await (await fetch("app.zip")).arrayBuffer();
    pyodide.unpackArchive(app, "zip", { extractDir: APP_DIR });
    pyodide.runPython(`import os, sys; os.chdir("${APP_DIR}"); sys.path.insert(0, "${APP_DIR}")`);

    window.openmatb = { pyodide }; // for debugging from the browser console
    status("Ready");
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
    status(`Loading failed: ${error}`);
    throw error;
});

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
    status("");
    try {
        await pyodide.runPythonAsync(`import runpy; runpy.run_path("main.py", run_name="__main__")`);
        $("pygletCanvas").focus();
    } catch (error) {
        status(`${error}`);
        console.error(error);
    }
});

// Dispatched when OpenMATB closes (end of scenario, replay closed or selection cancelled)
document.addEventListener("openmatb-exit", () => {
    if ($("end").hidden) {
        location.href = location.pathname; // back to the menu
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
