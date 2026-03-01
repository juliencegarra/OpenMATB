# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Thread
from time import sleep
from typing import Any, Callable

from core import validation
from core.constants import PATHS
from core.error import get_errors
from plugins.abstractplugin import AbstractPlugin

try:
    import cv2
except ImportError:
    cv2 = None


class Facecamera(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "invisible", taskupdatetime: int = 200) -> None:
        super().__init__(_("Face camera"), taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any]] = {
            "cameraindex": validation.is_natural_integer,
            "width": validation.is_positive_integer,
            "height": validation.is_positive_integer,
            "fps": validation.is_positive_integer,
            "codec": validation.is_string,
            "state": validation.is_string,
        }

        self.parameters.update(
            {
                "cameraindex": 0,
                "width": 640,
                "height": 480,
                "fps": 30,
                "codec": "mp4v",
            }
        )

        self._capture: Any | None = None
        self._writer: Any | None = None
        self._thread: Thread | None = None
        self._running: bool = False
        self._output_path: Path | None = None

    def _resolve_output_path(self) -> Path:
        logger_path: Path | None = getattr(self.logger, "path", None)
        if logger_path is not None:
            parent: Path = logger_path.parent
            stem: str = logger_path.stem
        else:
            parent = PATHS["SESSIONS"].joinpath(datetime.now().strftime("%Y-%m-%d"))
            stem = datetime.now().strftime("%y%m%d_%H%M%S")

        parent.mkdir(parents=True, exist_ok=True)
        return parent.joinpath(f"{stem}_facecamera.mp4")

    def _push_marker(self, marker: str) -> None:
        if self.logger.lsl is not None and hasattr(self.logger.lsl, "push"):
            self.logger.lsl.push(marker)

    def _close_io(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _capture_loop(self) -> None:
        frame_delay: float = 1.0 / float(max(1, int(self.parameters["fps"])))

        while self._running and self._capture is not None and self._writer is not None:
            ok, frame = self._capture.read()
            if ok:
                self._writer.write(frame)
            else:
                sleep(frame_delay)

    def start(self) -> None:
        super().start()

        if cv2 is None:
            get_errors().add_error(
                _("opencv-python is unavailable. Face camera recording is disabled."),
                fatal=False,
            )
            return

        self._output_path = self._resolve_output_path()

        self._capture = cv2.VideoCapture(int(self.parameters["cameraindex"]))
        if self._capture is None or not self._capture.isOpened():
            self._close_io()
            get_errors().add_error(_("Could not open the face camera device."), fatal=False)
            return

        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.parameters["width"]))
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.parameters["height"]))
        self._capture.set(cv2.CAP_PROP_FPS, float(self.parameters["fps"]))

        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._close_io()
            get_errors().add_error(_("Face camera opened, but no frame could be captured."), fatal=False)
            return

        height, width = frame.shape[:2]
        codec: str = str(self.parameters["codec"])
        if len(codec) != 4:
            codec = "mp4v"

        fourcc: Any = cv2.VideoWriter_fourcc(*codec)
        self._writer = cv2.VideoWriter(
            str(self._output_path),
            fourcc,
            float(self.parameters["fps"]),
            (int(width), int(height)),
        )
        if self._writer is None or not self._writer.isOpened():
            self._close_io()
            get_errors().add_error(_("Could not initialize the face camera video writer."), fatal=False)
            return

        self._writer.write(frame)
        self.logger.log_manual_entry(str(self._output_path), key="facecamera_path")
        self._push_marker("FACECAM_START")

        self._running = True
        self._thread = Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._push_marker("FACECAM_STOP")

        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        self._close_io()
        super().stop()
