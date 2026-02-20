# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any, Callable

from core import validation
from plugins.abstractplugin import AbstractPlugin


class Generictrigger(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "invisible", taskupdatetime: int = 5) -> None:
        super().__init__(_("Generic Trigger"), taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any]] = {"state": validation.is_string}

        self._last_trigger: str = ""
        self.parameters.update(
            {
                "state": self._last_trigger,
            }
        )
