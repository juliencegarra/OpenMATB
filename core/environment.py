# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""The computer running a desktop session, logged at its start: timing depends on the screen, the graphics card and
the power settings. Only the characteristics of the hardware: no computer or user name, no serial number.
(In the browser, see core.platform.browser_environment.)"""

from __future__ import annotations

import os
import platform
import sys
from typing import Any, Callable

import pyglet
from pyglet.display import get_display

from core import pyglet_compat
from core.platform import IS_WEB

Entries = list[tuple[str, str]]

AC_LINE_STATUS: dict[int, str] = {0: "battery", 1: "mains"}  # GetSystemPowerStatus; other values: unknown


def _screen_of(window: Any, screens: list[Any]) -> Any:
    """The screen showing the center of the window (window.screen is the default one for a window moved to the
    screen_index of config.ini)."""
    x, y = window.get_location()
    center_x, center_y = x + window.width / 2, y + window.height / 2
    for screen in screens:
        if screen.x <= center_x < screen.x + screen.width and screen.y <= center_y < screen.y + screen.height:
            return screen
    return window.screen


def _display_entries(window: Any) -> Entries:
    screens: list[Any] = get_display().get_screens()
    screen: Any = _screen_of(window, screens)
    mode: Any = screen.get_mode()
    return [
        ("screen", str(screen.get_monitor_name())),
        ("screen_mode", f"{mode.width}x{mode.height} {mode.rate}Hz {mode.depth}bit"),
        ("screen_scale", f"{screen.get_dpi()} dpi, scale {screen.get_scale()}"),
        ("screen_count", str(len(screens))),
        ("window_mode", "fullscreen" if window.fullscreen else "windowed"),
        ("vsync", str(window.vsync)),  # As requested: the driver can override it (see frame_median_ms at the end)
    ]


def _gpu_entries(window: Any) -> Entries:
    renderer, version = pyglet_compat.gpu_info(window)
    return [("gpu", str(renderer)), ("gpu_driver", str(version))]


def _software_entries() -> Entries:
    return [
        ("system", platform.platform()),
        ("python", platform.python_version()),
        ("pyglet", str(pyglet.version)),
    ]


def _cpu_name() -> str:
    """The commercial name of the processor, else the generic description (e.g. "Intel64 Family 6 Model 183")."""
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    if sys.platform == "darwin":
        import subprocess

        command: list[str] = ["sysctl", "-n", "machdep.cpu.brand_string"]
        return subprocess.run(command, capture_output=True, text=True, timeout=2, check=True).stdout.strip()
    with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo:
        for line in cpuinfo:
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor()


def _cpu_entries() -> Entries:
    try:
        name: str = _cpu_name()
    except Exception:  # Registry, /proc or sysctl: depends on the system
        name = platform.processor()
    entries: Entries = [("cpu", name)] if name else []
    cores: int | None = os.cpu_count()
    return [*entries, ("cpu_cores", str(cores))] if cores else entries


def _total_memory() -> int:
    """Physical memory, in bytes."""
    if sys.platform == "win32":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = (
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            )

        status: MEMORYSTATUSEX = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return status.ullTotalPhys
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


def _memory_entries() -> Entries:
    return [("ram", f"{_total_memory() / 2**30:.1f} GB")]


def _audio_entries() -> Entries:
    from pyglet.media import drivers

    return [("audio_driver", type(drivers.get_audio_driver()).__name__)]


def _power_entries() -> Entries:
    """Windows: on battery or power saving, the frames can be slower and less regular."""
    if sys.platform != "win32":
        return []
    import ctypes

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = (
            ("ACLineStatus", ctypes.c_ubyte),
            ("BatteryFlag", ctypes.c_ubyte),
            ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        )

    status: SYSTEM_POWER_STATUS = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return []
    source: str | None = AC_LINE_STATUS.get(status.ACLineStatus)
    if source is None:
        return []
    return [("power", f"{source}, battery saver" if status.SystemStatusFlag else source)]


def _power_plan_entries() -> Entries:
    """Windows: the name of the active power plan."""
    if sys.platform != "win32":
        return []
    import ctypes

    powrprof: Any = ctypes.windll.powrprof
    scheme: ctypes.c_void_p = ctypes.c_void_p()
    if powrprof.PowerGetActiveScheme(None, ctypes.byref(scheme)) != 0:
        return []
    try:
        size: ctypes.c_ulong = ctypes.c_ulong(0)
        powrprof.PowerReadFriendlyName(None, scheme, None, None, None, ctypes.byref(size))
        name: Any = ctypes.create_string_buffer(size.value)
        if powrprof.PowerReadFriendlyName(None, scheme, None, None, name, ctypes.byref(size)) != 0:
            return []
        return [("power_plan", ctypes.wstring_at(name))]
    finally:
        ctypes.windll.kernel32.LocalFree(scheme)


def system_environment(window: Any) -> Entries:
    """(key, value) entries describing the computer, for the session file. Empty in the browser."""
    if IS_WEB:
        return []
    probes: tuple[Callable[[], Entries], ...] = (
        lambda: _display_entries(window),
        lambda: _gpu_entries(window),
        _software_entries,
        _cpu_entries,
        _memory_entries,
        _audio_entries,
        _power_entries,
        _power_plan_entries,
    )
    entries: Entries = []
    for probe in probes:
        try:
            entries.extend(probe())
        except Exception:  # These details depend on the system and its drivers: never stop a session for them
            continue
    return entries
