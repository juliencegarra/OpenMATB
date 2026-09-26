# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Build the browser (Pyodide) version of OpenMATB into web/dist.

usage:
    python web/build.py            # build web/dist
    python web/build.py --serve    # build, then serve on http://localhost:8000
    python web/build.py --pyodide local   # ship Pyodide with the page instead of loading it from its CDN
    python web/build.py --scorm    # also write web/openmatb_scorm_1.2.zip, to import into an LMS
    python web/build.py --scorm 2004
    python web/build.py --release DIR     # the packages of a release, with fixed names (see RELEASE_PACKAGES)

The page must be served over HTTP (file:// does not work). The output is static
and can be hosted anywhere (GitHub Pages, a lab server...).

SCORM and release packages ship Pyodide (LMSs and JATOS servers may block external scripts), unless --pyodide cdn.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import io
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT: Path = Path(__file__).resolve().parent.parent
WEB: Path = ROOT / "web"
DIST: Path = WEB / "dist"

# Keep in sync with requirements.txt
WHEELS: list[str] = ["pyglet==3.0.dev10", "rstr==3.1.0"]

# JavaScript modules of the page (web/*.js), copied as is
PAGE_MODULES: tuple[str, ...] = ("openmatb.js", "session_output.js", "scorm.js")

PYODIDE_VERSION: str = "0.29.4"
PYODIDE_CDN: str = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
# What the page needs to run Pyodide from web/dist/pyodide (--pyodide local): CDN name -> local name, plus the
# packages it loads. The ES module is renamed .js: many servers (Python's on Windows, some LMSs) serve .mjs as
# text/plain, which browsers refuse for a module.
PYODIDE_FILES: dict[str, str] = {
    "pyodide.mjs": "pyodide-module.js",
    "pyodide.asm.js": "pyodide.asm.js",
    "pyodide.asm.wasm": "pyodide.asm.wasm",
    "python_stdlib.zip": "python_stdlib.zip",
    "pyodide-lock.json": "pyodide-lock.json",
}
PYODIDE_PACKAGES: tuple[str, ...] = ("micropip",)
# The Pyodide module imported by the page (<meta name="pyodide-module"> of index.html)
PYODIDE_MODULES: dict[str, str] = {"cdn": PYODIDE_CDN + "pyodide.mjs", "local": "pyodide/pyodide-module.js"}

SCORM_VERSIONS: tuple[str, ...] = ("1.2", "2004")

# JATOS study: fixed identifiers, so that importing a new version updates the study already imported
JATOS_STUDY_UUID: str = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/juliencegarra/OpenMATB/jatos/study"))
JATOS_COMPONENT_UUID: str = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/juliencegarra/OpenMATB/jatos/page"))
JATOS_STUDY_DIR: str = "openmatb"
JATOS_WORKER_TYPES: list[str] = ["Jatos", "PersonalSingle", "PersonalMultiple", "GeneralSingle", "GeneralMultiple"]

# Files of a release (python web/build.py --release DIR), linked by the website (releases/latest/download/<name>)
RELEASE_PACKAGES: dict[str, str] = {
    "web": "OpenMATB-Web.zip",
    "jatos": "OpenMATB-JATOS.jzip",
    "scorm-1.2": "OpenMATB-SCORM-1.2.zip",
    "scorm-2004": "OpenMATB-SCORM-2004.zip",
}

# Browsers have no common sans-serif font name that pyglet can use: ship one (SIL Open Font License)
FONT_URL: str = "https://cdn.jsdelivr.net/npm/@fontsource/noto-sans@5.3.0/files/noto-sans-latin-{weight}-normal.woff2"
FONT_WEIGHTS: tuple[int, ...] = (400, 700)

# Application files packed into app.zip, then extracted into the Pyodide file system
APP_FILES: list[str] = ["main.py", "config.ini", "VERSION"]
APP_DIRS: dict[str, tuple[str, ...]] = {
    "core": ("*.py",),
    "plugins": ("*.py",),
    "locales": ("*.mo",),
    "includes/img": ("*",),
    "includes/instructions": ("*",),
    "includes/questionnaires": ("*",),
    "includes/scenarios": ("*.txt",),
    "includes/sounds": ("*.wav",),
}
# Not usable in the browser (native libraries) or not part of the task
EXCLUDED: tuple[str, ...] = ("plugins/eyetracker.py", "includes/scenarios/generated")


def is_excluded(relative: str) -> bool:
    return any(relative == e or relative.startswith(e + "/") for e in EXCLUDED)


def build_app_zip() -> int:
    count: int = 0
    with zipfile.ZipFile(DIST / "app.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in APP_FILES:
            archive.write(ROOT / name, name)
            count += 1
        for folder, patterns in APP_DIRS.items():
            for pattern in patterns:
                for path in sorted((ROOT / folder).rglob(pattern)):
                    relative: str = path.relative_to(ROOT).as_posix()
                    if path.is_file() and "__pycache__" not in relative and not is_excluded(relative):
                        archive.write(path, relative)
                        count += 1
    return count


def download_wheels() -> list[str]:
    wheels_dir: Path = DIST / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:", "-q", "-d", str(wheels_dir)]
        + WHEELS,
        check=True,
    )
    return sorted(p.name for p in wheels_dir.glob("*.whl"))


def copy_pyglet_bridge() -> None:
    """pyglet ships the JavaScript side of its browser backend inside the wheel."""
    with zipfile.ZipFile(next((DIST / "wheels").glob("pyglet-*.whl"))) as wheel:
        (DIST / "pyglet_emscripten.js").write_bytes(wheel.read("pyglet/libs/emscripten/pyglet_emscripten.js"))


def download_fonts() -> None:
    fonts_dir: Path = DIST / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for weight in FONT_WEIGHTS:
        with urllib.request.urlopen(FONT_URL.format(weight=weight)) as response:
            (fonts_dir / f"noto-sans-{weight}.woff2").write_bytes(response.read())


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response:
        path.write_bytes(response.read())


def pyodide_package_files(lock: dict, packages: tuple[str, ...]) -> list[str]:
    """Files of the Pyodide packages loaded by the page, with their dependencies (from pyodide-lock.json)."""
    files: list[str] = []
    todo: list[str] = list(packages)
    seen: set[str] = set()
    while todo:
        name: str = todo.pop(0)
        if name in seen:
            continue
        seen.add(name)
        package: dict = lock["packages"][name]
        files.append(package["file_name"])
        todo.extend(package.get("depends", []))
    return files


def download_pyodide() -> None:
    folder: Path = DIST / "pyodide"
    for name, local_name in PYODIDE_FILES.items():
        download(PYODIDE_CDN + name, folder / local_name)
    lock: dict = json.loads((folder / "pyodide-lock.json").read_text(encoding="utf-8"))
    for name in pyodide_package_files(lock, PYODIDE_PACKAGES):
        download(PYODIDE_CDN + name, folder / name)


def build(pyodide: str = "cdn") -> None:
    # Empty the folder rather than deleting it (it may be the working directory of a running server)
    DIST.mkdir(parents=True, exist_ok=True)
    for child in DIST.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()

    wheels: list[str] = download_wheels()
    copy_pyglet_bridge()
    download_fonts()
    for module in PAGE_MODULES:
        shutil.copy(WEB / module, DIST / module)
    version: str = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if pyodide == "local":
        download_pyodide()
    index: str = (
        (WEB / "index.html")
        .read_text(encoding="utf-8")
        .replace("{{VERSION}}", version)
        .replace("{{PYODIDE_MODULE}}", PYODIDE_MODULES[pyodide])
    )
    (DIST / "index.html").write_text(index, encoding="utf-8")
    shutil.copy(ROOT / "includes" / "img" / "logo32.png", DIST / "favicon.png")
    (DIST / "wheels.txt").write_text("\n".join(wheels) + "\n", encoding="utf-8")
    count: int = build_app_zip()

    size_mb: float = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file()) / 1e6
    print(f"Built {DIST} ({count} app files, wheels: {', '.join(wheels)}, Pyodide: {pyodide}, {size_mb:.1f} MB)")


# Namespaces of imsmanifest.xml
SCORM_NAMESPACES: dict[str, str] = {
    "1.2": """xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
        http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd\"""",
    "2004": """xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_v1p3"
    xmlns:adlseq="http://www.adlnet.org/xsd/adlseq_v1p3"
    xmlns:adlnav="http://www.adlnet.org/xsd/adlnav_v1p3"
    xmlns:imsss="http://www.imsglobal.org/xsd/imsss"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imscp_v1p1 imscp_v1p1.xsd
        http://www.adlnet.org/xsd/adlcp_v1p3 adlcp_v1p3.xsd
        http://www.adlnet.org/xsd/adlseq_v1p3 adlseq_v1p3.xsd
        http://www.adlnet.org/xsd/adlnav_v1p3 adlnav_v1p3.xsd
        http://www.imsglobal.org/xsd/imsss imsss_v1p0.xsd\"""",
}
SCORM_SCHEMA_VERSIONS: dict[str, str] = {"1.2": "1.2", "2004": "2004 4th Edition"}
SCORM_TYPE_ATTRIBUTES: dict[str, str] = {"1.2": "adlcp:scormtype", "2004": "adlcp:scormType"}


def scorm_manifest(scorm_version: str, title: str, version: str, files: list[str]) -> str:
    """imsmanifest.xml of a package with a single SCO (the page), SCORM 1.2 or 2004 (4th edition)."""
    if scorm_version not in SCORM_VERSIONS:
        raise ValueError(f"unknown SCORM version {scorm_version!r} ({', '.join(SCORM_VERSIONS)})")
    identifier: str = "OpenMATB-" + "".join(c if c.isalnum() else "-" for c in version)
    scorm_type: str = SCORM_TYPE_ATTRIBUTES[scorm_version]
    file_list: str = "\n".join(f"      <file href={quoteattr(name)}/>" for name in files)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{identifier}" version="1.0"
    {SCORM_NAMESPACES[scorm_version]}>
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>{SCORM_SCHEMA_VERSIONS[scorm_version]}</schemaversion>
  </metadata>
  <organizations default="openmatb">
    <organization identifier="openmatb">
      <title>{escape(title)}</title>
      <item identifier="openmatb-item" identifierref="openmatb-page" isvisible="true">
        <title>{escape(title)}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="openmatb-page" type="webcontent" {scorm_type}="sco" href="index.html">
{file_list}
    </resource>
  </resources>
</manifest>
"""


def dist_files() -> list[str]:
    return sorted(p.relative_to(DIST).as_posix() for p in DIST.rglob("*") if p.is_file())


def app_zip_with_config(overrides: dict[str, str]) -> bytes:
    """app.zip of web/dist with other config.ini values (e.g. web_session_output=jatos for the JATOS study)."""
    source = zipfile.ZipFile(DIST / "app.zip")
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in source.infolist():
            data: bytes = source.read(item)
            if item.filename == "config.ini":
                text: str = data.decode("utf-8")
                for key, value in overrides.items():
                    text, count = re.subn(rf"(?m)^{key}=.*$", f"{key}={value}", text)
                    if not count:
                        raise KeyError(f"{key} is not in config.ini")
                data = text.encode("utf-8")
            archive.writestr(item, data)
    return output.getvalue()


def write_package(
    package: Path, prefix: str = "", extra: dict[str, str] | None = None, config: dict[str, str] | None = None
) -> Path:
    """Zip web/dist under prefix, with extra files (name -> text) and other config.ini values."""
    package.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in (extra or {}).items():
            archive.writestr(name, text)
        for name in dist_files():
            if name == "app.zip" and config:
                archive.writestr(prefix + name, app_zip_with_config(config))
            else:
                archive.write(DIST / name, prefix + name)
    print(f"{package.name}: {package} ({package.stat().st_size / 1e6:.1f} MB)")
    return package


def build_scorm_package(scorm_version: str, title: str = "OpenMATB", package: Path | None = None) -> Path:
    """Zip web/dist with its imsmanifest.xml: the package to import into an LMS (Moodle, SCORM Cloud...)."""
    version: str = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest: str = scorm_manifest(scorm_version, title, version, dist_files())
    return write_package(package or WEB / f"openmatb_scorm_{scorm_version}.zip", extra={"imsmanifest.xml": manifest})


def jatos_study(title: str, version: str) -> dict:
    """The .jas file of a JATOS study archive: one component (the page), one batch."""
    return {
        "version": "3",
        "data": {
            "uuid": JATOS_STUDY_UUID,
            "title": title,
            "description": f"OpenMATB {version} (web version). Session files are saved in the results.",
            "groupStudy": False,
            "linearStudy": False,
            "allowPreview": False,
            "dirName": JATOS_STUDY_DIR,
            "comments": None,
            "jsonData": None,
            "endRedirectUrl": None,
            "studyEntryMsg": None,
            "componentList": [
                {
                    "uuid": JATOS_COMPONENT_UUID,
                    "title": "OpenMATB",
                    "htmlFilePath": "index.html",
                    "reloadable": False,
                    "active": True,
                    "comments": None,
                    "jsonData": None,
                }
            ],
            "batchList": [
                {
                    "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{JATOS_STUDY_UUID}/batch")),
                    "title": "Default",
                    "active": True,
                    "maxActiveMembers": None,
                    "maxTotalMembers": None,
                    "maxTotalWorkers": None,
                    "allowedWorkerTypes": JATOS_WORKER_TYPES,
                    "comments": None,
                    "jsonData": None,
                }
            ],
        },
    }


def build_jatos_package(package: Path, title: str = "OpenMATB") -> Path:
    """JATOS study archive (.jzip, imported with Import Study): web/dist in the study folder, and the session
    files sent to JATOS (web_session_output=jatos)."""
    version: str = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    jas: str = json.dumps(jatos_study(title, version), indent=2)
    return write_package(
        package,
        prefix=f"{JATOS_STUDY_DIR}/",
        extra={f"{JATOS_STUDY_DIR}.jas": jas},
        config={"web_session_output": "jatos"},
    )


def build_release(folder: Path) -> list[Path]:
    """The web packages of a release: static site to host, JATOS study, SCORM 1.2 and 2004 packages."""
    return [
        write_package(folder / RELEASE_PACKAGES["web"], prefix="OpenMATB-Web/"),
        build_jatos_package(folder / RELEASE_PACKAGES["jatos"]),
        build_scorm_package("1.2", package=folder / RELEASE_PACKAGES["scorm-1.2"]),
        build_scorm_package("2004", package=folder / RELEASE_PACKAGES["scorm-2004"]),
    ]


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    with http.server.ThreadingHTTPServer(("localhost", port), handler) as server:
        print(f"Serving on http://localhost:{port}/  (Ctrl+C to stop)")
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serve", action="store_true", help="serve web/dist after building")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--pyodide",
        choices=("cdn", "local"),
        default=None,
        help="load Pyodide from its CDN (default) or ship it in web/dist (default with --scorm)",
    )
    parser.add_argument(
        "--scorm",
        nargs="?",
        const="1.2",
        choices=SCORM_VERSIONS,
        default=None,
        help="also write a SCORM package, web/openmatb_scorm_<version>.zip (1.2 by default, or 2004)",
    )
    parser.add_argument("--scorm-title", default="OpenMATB", help="title of the activity in the LMS")
    parser.add_argument(
        "--release", type=Path, metavar="DIR", help="write the web packages of a release into DIR (fixed names)"
    )
    args = parser.parse_args()
    build(args.pyodide or ("local" if args.scorm or args.release else "cdn"))
    if args.scorm:
        build_scorm_package(args.scorm, args.scorm_title)
    if args.release:
        build_release(args.release)
    if args.serve:
        serve(args.port)
