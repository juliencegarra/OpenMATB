// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// The session files kept in this browser (replay, download again), one IndexedDB entry per file.
//
// They were kept in /data, mounted by pyglet with Emscripten's IDBFS, which copies every file of its database in
// memory at each start of the page (a synchronous file system cannot read IndexedDB on demand): a lab computer
// running many sessions in a browser (about 76 MB per hour of session) started slower and slower, up to a page out
// of memory. Pyodide's OPFS mount (mountNativeFS) works the same way. The files are now read and written one at a
// time, in the same database and with the same entries as IDBFS: the sessions kept before are read as they are.
//
// The running session is written in the Pyodide file system (memory), and saved here at each checkpoint (every
// 10 s) and at its end. A session is copied in the file system only to be replayed.
//
// A file larger than CHUNK_SIZE is kept in parts (entries "<path>.part<n>", its entry gives their number): Chromium
// refuses an IndexedDB value of more than 133 MB, so IDBFS could not keep a session of more than about 1 h 45.

const DB_NAME = "/data"; // IDBFS: the mount point
const DB_VERSION = 21; // IDBFS.DB_VERSION
const STORE = "FILE_DATA"; // IDBFS.DB_STORE_NAME
const FILE_MODE = 0o100644; // A regular file (IDBFS keeps the mode of each entry)
const DIR_MODE = 0o40755; // A folder: IDBFS creates the folders of its entries from their own entries

const CHUNK_SIZE = 64 * 1024 * 1024;

export const SESSIONS_DIR = "/data/openmatb/sessions"; // pyglet.storage.get("openmatb").data / "sessions"

let database = null;

function done(request) {
    return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function finished(transaction) {
    return new Promise((resolve, reject) => {
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
    });
}

async function open() {
    if (!database) {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => { // As IDBFS: the store of the entries, indexed by their time
            const store = request.result.objectStoreNames.contains(STORE)
                ? request.transaction.objectStore(STORE)
                : request.result.createObjectStore(STORE);
            if (!store.indexNames.contains("timestamp")) {
                store.createIndex("timestamp", "timestamp", { unique: false });
            }
        };
        database = done(request);
    }
    return database;
}

// The session files (.csv), the most recent first: {path, name, folder, size, time}. Their entries are read one
// at a time (a cursor), none is kept in memory
export async function listSessions() {
    const store = (await open()).transaction(STORE, "readonly").objectStore(STORE);
    const range = IDBKeyRange.bound(`${SESSIONS_DIR}/`, `${SESSIONS_DIR}/\uffff`);
    const sessions = [];
    await new Promise((resolve, reject) => {
        const request = store.openCursor(range);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            const cursor = request.result;
            if (!cursor) {
                resolve();
                return;
            }
            const path = String(cursor.key);
            const entry = cursor.value;
            if ((entry.contents || entry.parts) && path.endsWith(".csv")) {
                const folder = path.slice(SESSIONS_DIR.length + 1, path.lastIndexOf("/") + 1).replace(/\/$/, "");
                const time = new Date(entry.timestamp).getTime();
                const size = entry.parts ? entry.size : entry.contents.byteLength;
                sessions.push({ path, name: path.split("/").pop(), folder, size, time });
            }
            cursor.continue();
        };
    });
    return sessions.sort((a, b) => b.time - a.time);
}

// The contents (Uint8Array) of a kept file, null if it is not kept
export async function readSession(path) {
    const store = (await open()).transaction(STORE, "readonly").objectStore(STORE);
    const entry = await done(store.get(path));
    if (entry?.contents) {
        return new Uint8Array(entry.contents);
    }
    if (!entry?.parts) {
        return null;
    }
    const contents = new Uint8Array(entry.size);
    let offset = 0;
    for (let n = 0; n < entry.parts; n++) {
        const part = await done(store.get(`${path}.part${n}`));
        contents.set(part, offset);
        offset += part.byteLength;
    }
    return contents;
}

// Keep a file (contents: Uint8Array or text), with the entries of its folders (as IDBFS: a version of OpenMATB
// mounting /data again reads it)
export async function writeSession(path, contents) {
    const bytes = typeof contents === "string" ? new TextEncoder().encode(contents) : new Uint8Array(contents);
    const transaction = (await open()).transaction(STORE, "readwrite");
    const store = transaction.objectStore(STORE);
    const now = new Date();
    const names = path.split("/").filter((name) => name);
    for (let n = 1; n < names.length; n++) {
        const folder = `/${names.slice(0, n).join("/")}`;
        const request = store.getKey(folder);
        request.onsuccess = () => {
            if (request.result === undefined) {
                store.put({ timestamp: now, mode: DIR_MODE }, folder);
            }
        };
    }
    store.delete(IDBKeyRange.bound(`${path}.part`, `${path}.part\uffff`)); // The parts of a former version
    if (bytes.byteLength <= CHUNK_SIZE) {
        store.put({ timestamp: now, mode: FILE_MODE, contents: bytes }, path);
    } else {
        const parts = Math.ceil(bytes.byteLength / CHUNK_SIZE);
        for (let n = 0; n < parts; n++) {
            store.put(bytes.slice(n * CHUNK_SIZE, (n + 1) * CHUNK_SIZE), `${path}.part${n}`);
        }
        store.put({ timestamp: now, mode: FILE_MODE, parts, size: bytes.byteLength }, path);
    }
    await finished(transaction);
}

export async function deleteSession(path) {
    const transaction = (await open()).transaction(STORE, "readwrite");
    const store = transaction.objectStore(STORE);
    store.delete(path);
    store.delete(IDBKeyRange.bound(`${path}.part`, `${path}.part\uffff`));
    await finished(transaction);
}

// Copy kept sessions in the Pyodide file system, to be replayed: those of a session number (?session=), else all
// (the selector of the replay lists the files)
export async function loadSessionsForReplay(pyodide, sessionNumber = null) {
    const prefix = sessionNumber === null ? null : `${sessionNumber}_`;
    for (const session of await listSessions()) {
        if (prefix !== null && !session.name.startsWith(prefix)) {
            continue;
        }
        const contents = await readSession(session.path);
        pyodide.FS.mkdirTree(session.path.slice(0, session.path.lastIndexOf("/")));
        pyodide.FS.writeFile(session.path, contents);
    }
}
