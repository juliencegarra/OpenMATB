# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from pathlib import Path
from typing import Any

import plugins  # noqa: F401 — needed by globals()["plugins"] for dynamic plugin loading
from core import validation
from core.constants import DEPRECATED, REPLAY_MODE, SYSTEM_COMMANDS, SYSTEM_PSEUDO_PLUGIN
from core.constants import PATHS as P
from core.error import get_errors
from core.event import Event
from core.logger import get_logger
from core.utils import get_conf_value


class Scenario:
    """
    This object converts scenario to Events, loads the corresponding plugins,
    and checks that some criteria are met (e.g., acceptable values)
    """

    def __init__(self, contents: list[str] | None = None, scenario_path: Path | None = None) -> None:
        self.events: list[Event] = list()
        self.plugins: dict[str, Any] = dict()

        if contents is None:
            if scenario_path is not None:
                sp: Path = scenario_path
            else:
                sp = P["SCENARIOS"].joinpath(get_conf_value("Openmatb", "scenario_path"))

            if sp.exists():
                with open(sp, "r") as f:
                    contents = f.readlines()
                get_logger().log_manual_entry(sp, key="scenario_path")
            else:
                get_errors().add_error(_("%s was not found") % str(sp), fatal=True)

        # Convert the scenario content into a list of events #
        # (Squeeze empty and commented [#] lines)
        self.events = [
            Event.parse_from_string(line_n, line_str)
            for line_n, line_str in enumerate(contents)
            if len(line_str.strip()) > 0 and not line_str.startswith("#")
        ]

        # Next load the scheduled plugins into the class, so we can check potential errors
        # But first, check that only available plugins are mentioned
        for event in self.events:
            if event.plugin == SYSTEM_PSEUDO_PLUGIN:
                continue
            if not hasattr(globals()["plugins"], event.plugin.capitalize()):
                get_errors().add_error(
                    _("Scenario error: %s is not a valid plugin name (l. %s)") % (event.plugin, event.line), fatal=True
                )

        self.plugins = {
            name: getattr(globals()["plugins"], name.capitalize())() for name in self.get_plugins_name_list()
        }

        self.events = self.events_retrocompatibility()  # Apply retrocompatiblity to events
        event_errors: list[str] = self.check_events()  # Check that events are properly expressed

        with open(P["SCENARIO_ERRORS"], "w") as errorf:
            if len(event_errors) > 0:
                for this_error in event_errors:
                    print(this_error, file=errorf)
            else:
                print(_("No error"), file=errorf)

        if len(event_errors) > 0:
            get_errors().add_error(
                _("There were some errors in the scenario. See the %s file.") % P["SCENARIO_ERRORS"].name, fatal=True
            )

    def reload_plugins(self) -> None:
        for name, plugin in self.plugins.items():
            for _w, widget in plugin.widgets.items():
                widget.empty_batch()

            plugin.widgets = dict()

            del plugin

            if hasattr(globals()["plugins"], name):
                delattr(globals()["plugins"], name)

            # Instantiate plugins
            self.plugins[name] = getattr(globals()["plugins"], name.capitalize())()

    def events_retrocompatibility(self) -> list[Event]:
        new_list: list[Event] = list()
        for _n, e in enumerate(self.events):
            # If plugin or command is DEPRECATED, ignore the event
            if e.is_deprecated():
                pass  # TODO: Raise a deprecation warning

            # For parameters
            # SYSMON now manages failures with two separated variables
            elif (
                len(e) == 2
                and "scales" in e.command[0]
                and "failure" in e.command[0]
                and e.command[1] in ["up", "down"]
            ):
                sysmon_dict: dict[str, str] = dict(up="1", down="-1")
                command_1: list[str] = [e.command[0], "True"]
                command_2: list[str] = [e.command[0].replace("failure", "side"), sysmon_dict[e.command[1]]]
                new_list.append(Event(e.line, e.time_sec, e.plugin, command_1))
                new_list.append(Event(e.line, e.time_sec, e.plugin, command_2))

            # If no retrocompatibility to apply, just append the event
            else:
                new_list.append(e)
        return new_list

    def get_parameters_value(self, plugin: str, command: list[str]) -> tuple[Any, bool]:
        current_level: Any = self.plugins[plugin].parameters
        parameter_address: list[str] = command[0].split("-")

        for entry in parameter_address:  # Is this parameter existing ?
            if current_level is not None and entry in current_level:
                if isinstance(current_level[entry], dict):
                    current_level = current_level[entry]
            else:  # Not entry found, try to resolve retrocompatiblity issue
                current_level = None

        if current_level is None:
            return None, False
        else:
            return current_level[parameter_address[-1]], True

    def try_retrocompatibility(self, plugin: str, command: list[str]) -> tuple[Any, bool | None]:
        try:
            command[0] = retro[command[0]]  # noqa: F821
        except KeyError:
            return None, None
        else:
            return self.get_parameters_value(plugin, command)

    def get_plugin_methods(self, plugin: str) -> list[str]:
        return [f for f in dir(self.plugins[plugin]) if callable(getattr(self.plugins[plugin], f))]

    def get_plugin_events(self, plugin_name: str) -> list[Event]:
        return [e for e in self.events if e.plugin == plugin_name]

    def check_events(self) -> list[str]:
        errors: list[str] = list()

        # Rule 1 - all the mentioned plugins should have a start and a stop commands
        # Only non-blocking plugins must have a stop command
        for plug_name in self.get_plugins_name_list():
            if not any(["start" in e.command for e in self.get_plugin_events(plug_name)]):
                errors.append(_("The (%s) plugin does not have a start command.") % plug_name)

            if self.plugins[plug_name].blocking is False:
                if not REPLAY_MODE:
                    if not any(["stop" in e.command for e in self.get_plugin_events(plug_name)]):
                        errors.append(_("The (%s) plugin does not have a stop command.") % plug_name)
                else:
                    pass  # Not a problem during a replay (because a scenario can have been exited
                    # manually before the end, it's not mandatory to have it)

        # Rule 1 bis - As for the blocking plugins, they should have their input file
        # defined before they start (check that each start command is preceeded by filename information)
        ## TODO

        for e in self.events:
            # System pseudo-plugin: validate command and skip plugin checks
            if e.plugin == SYSTEM_PSEUDO_PLUGIN:
                if len(e.command) != 1 or e.command[0] not in SYSTEM_COMMANDS:
                    errors.append(_("Error on line %s. Invalid system command: %s") % (e.line, e.get_command_str()))
                continue

            # Rule 2 - all events should trigger a command to a plugin
            if len(e) == 0:
                errors.append(_("Error on line %s. This event does not trigger any command.") % e.line)

            # Rule 2 bis - maximum length of a command is 2 (parameter;value)
            elif len(e) > 2:
                errors.append(_("Error on line %s. Maximum length of an event is 2 (parameter;value).") % e.line)

            # Rule 3 - when present, a command should match either a plugin method or
            # a parameter, the value of the latter being acceptable
            elif len(e) == 1:  # Method expected
                if e.command[0] not in self.get_plugin_methods(e.plugin):
                    errors.append(
                        _("Error on line %s. Method (%s) is not available for the plugin (%s)")
                        % (e.line, e.command[0], e.plugin)
                    )

            elif len(e) == 2:  # Parameter expected
                _current_value, exists = self.get_parameters_value(e.plugin, e.command)

                # If the current parameter exists in the plugin
                if exists:
                    method_args: list[Any] | None = None

                    # Check that the parameter has a verification method
                    # either globally or in the plugins itself
                    # Else trigger a warning (should not happen)
                    validation_dict: dict[str, Any] = self.get_validation_dict(e.plugin)

                    if e.command[0] in validation_dict:
                        eval_method: Any = validation_dict[e.command[0]]
                    else:
                        eval_method = None
                        errors.append(
                            _("Warning on line %s. Parameter (%s) has no verification method") % (e.line, e.command[0])
                        )

                    if eval_method is not None:
                        if isinstance(eval_method, tuple):
                            # Method-args will receive extra arguments
                            eval_method, *method_args = eval_method

                        # Remove potential blank spaces in the command argument
                        # (except is the eval_method is waiting for a string, like title)
                        if eval_method.__name__ != "is_string":
                            e.command[1] = e.command[1].replace(" ", "")

                        # ...extra arguments are unpacked here if present
                        method_args = (e.command[1], *method_args) if method_args is not None else (e.command[1],)
                        eval_value, error = eval_method(*method_args)

                        if error is not None:
                            preamble: str = _("Error on line %s. %s ") % (e.line, e.command[0])
                            error_msg: str = preamble + error
                            errors.append(error_msg)
                        else:
                            # If no error, replace the event value by its evaluated version
                            e.command[1] = eval_value
                else:
                    errors.append(
                        _("Error on line %s. The %s plugin does not have a %s parameter")
                        % (e.line, e.plugin, e.command[-2])
                    )
        return errors

    def get_validation_dict(self, pluginname: str) -> dict[str, Any]:
        validation_dict: dict[str, Any] = global_validation_dict.copy()

        plugin_validation_dict: dict[str, Any] | None = getattr(self.plugins[pluginname], "validation_dict", None)

        if plugin_validation_dict is not None:
            validation_dict.update(plugin_validation_dict)

        return validation_dict

    def get_plugins_name_list(self) -> set[str]:
        return set([e.plugin for e in self.events if e.plugin not in DEPRECATED and e.plugin != SYSTEM_PSEUDO_PLUGIN])


# This dictionary associates to each parameter name a checking method
# TODO: probably move each of them to plugins to remove any global parameter
global_validation_dict: dict[str, Any] = {
    # If the key points to a tuple, the first argument is the method
    # the other arguments are extra-method arguments
    # General values #
    "title": validation.is_string,
    "taskplacement": validation.is_task_location,
    "taskupdatetime": validation.is_positive_integer,
    # Shared values # TODO: move to each plugin
    "automaticsolver": validation.is_boolean,
    "displayautomationstate": validation.is_boolean,
    "taskfeedback-overdue-active": validation.is_boolean,
    "taskfeedback-overdue-color": validation.is_color,
    "taskfeedback-overdue-delayms": validation.is_natural_integer,
    "taskfeedback-overdue-blinkdurationms": validation.is_natural_integer,
    # (sysmon & communications)
    "feedbackduration": validation.is_positive_integer,
    "feedbacks-positive-active": validation.is_boolean,
    "feedbacks-positive-color": validation.is_color,
    "feedbacks-negative-active": validation.is_boolean,
    "feedbacks-negative-color": validation.is_color,
    # Blocking plugins (genericscales, instructions)
    "boldtitle": validation.is_boolean,
    "filename": validation.is_available_text_file,
    "pointsize": validation.is_natural_integer,
    "maxdurationsec": validation.is_natural_integer,
    "response-text": validation.is_string,
    "response-key": validation.is_keyboard_key,
    "allowkeypress": validation.is_boolean,
}
