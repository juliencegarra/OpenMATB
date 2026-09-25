# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Build the browser (Pyodide) version of OpenMATB into web/dist.

usage:
    python web/build.py            # build web/dist
    python web/build.py --serve    # build, then serve on http://localhost:8000

The page must be served over HTTP (file:// does not work). The output is static
and can be hosted anywhere (GitHub Pages, a lab server...).
"""

from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent
WEB: Path = ROOT / "web"
DIST: Path = WEB / "dist"

# Keep in sync with requirements.txt
WHEELS: list[str] = ["pyglet==3.0.dev10", "rstr==3.1.0"]

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


def build() -> None:
    # Empty the folder rather than deleting it (it may be the working directory of a running server)
    DIST.mkdir(parents=True, exist_ok=True)
    for child in DIST.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()

    wheels: list[str] = download_wheels()
    copy_pyglet_bridge()
    download_fonts()
    for name in ("index.html", "openmatb.js"):
        shutil.copy(WEB / name, DIST / name)
    shutil.copy(ROOT / "includes" / "img" / "logo32.png", DIST / "favicon.png")
    (DIST / "wheels.txt").write_text("\n".join(wheels) + "\n", encoding="utf-8")
    count: int = build_app_zip()

    size_mb: float = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file()) / 1e6
    print(f"Built {DIST} ({count} app files, wheels: {', '.join(wheels)}, {size_mb:.1f} MB)")


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    with http.server.ThreadingHTTPServer(("localhost", port), handler) as server:
        print(f"Serving on http://localhost:{port}/  (Ctrl+C to stop)")
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serve", action="store_true", help="serve web/dist after building")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    build()
    if args.serve:
        serve(args.port)
