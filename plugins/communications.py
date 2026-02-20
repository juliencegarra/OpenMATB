# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from math import copysign
from pathlib import Path
from string import ascii_lowercase, ascii_uppercase, digits
from typing import Any, Callable, Optional

from pyglet.media import Player, SourceGroup, load

from core import validation
from core.constants import COLORS as C
from core.constants import PATHS as P
from core.constants import REPLAY_MODE
from core.container import Container
from core.pseudorandom import choice, randint, uniform, xeger
from core.widgets import Radio, Simpletext
from plugins.abstractplugin import AbstractPlugin


class Communications(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "bottomleft", taskupdatetime: int = 80) -> None:
        super().__init__(_("Communications"), taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any] | tuple[Callable[..., Any], list[str]]] = {
            "owncallsign": validation.is_callsign,
            "othercallsign": validation.is_callsign_or_list_of,  # othercallsign can be a list of callsigns
            "voiceidiom": (validation.is_in_list, [p.name.lower() for p in P["SOUNDS"].iterdir()]),
            "voicegender": (
                validation.is_in_list,
                list(
                    set(
                        d.name.lower()
                        for idiom in P["SOUNDS"].iterdir()
                        if idiom.is_dir()
                        for d in idiom.iterdir()
                        if d.is_dir()
                    )
                ),
            ),
            "othercallsignnumber": validation.is_positive_integer,
            "airbandminMhz": validation.is_positive_float,
            "airbandmaxMhz": validation.is_positive_float,
            "airbandminvariationMhz": validation.is_positive_integer,
            "airbandmaxvariationMhz": validation.is_positive_integer,
            "radioprompt": (validation.is_in_list, ["own", "other"]),
            "promptlist": (validation.is_in_list, ["NAV_1", "NAV_2", "COM_1", "COM_2"]),
            "maxresponsedelay": validation.is_positive_integer,
            "callsignregex": validation.is_a_regex,
            "keys-selectradioup": validation.is_key,
            "keys-selectradiodown": validation.is_key,
            "keys-tunefrequencyup": validation.is_key,
            "keys-tunefrequencydown": validation.is_key,
            "keys-validateresponse": validation.is_key,
        }

        self.keys: set[str] = {"UP", "DOWN", "RIGHT", "LEFT", "ENTER"}
        self.callsign_seed: int = 1  # Useful to pseudorandomly generate different callsign when
        # trying to generate multiple callsigns at once

        self.letters: str = ascii_uppercase
        self.digits: str = digits

        # Callsign regex must be defined first because it is needed by self.get_callsign()
        self.parameters["callsignregex"] = r"[A-Z][A-Z][A-Z]\d\d\d"
        self.old_regex: str = str(self.parameters["callsignregex"])
        new_par: dict[str, Any] = dict(
            owncallsign="",
            othercallsign=list(),
            othercallsignnumber=5,
            airbandminMhz=108.0,
            airbandmaxMhz=137.0,
            airbandminvariationMhz=5,
            airbandmaxvariationMhz=6,
            voicegender="female",
            voiceidiom="french",
            radioprompt="",
            maxresponsedelay=20000,
            promptlist=["NAV_1", "NAV_2", "COM_1", "COM_2"],
            automaticsolver=False,
            displayautomationstate=True,
            feedbackduration=1500,
            feedbacks=dict(positive=dict(active=False, color=C["GREEN"]), negative=dict(active=False, color=C["RED"])),
            keys=dict(
                selectradioup="UP",
                selectradiodown="DOWN",
                tunefrequencyup="RIGHT",
                tunefrequencydown="LEFT",
                validateresponse="ENTER",
            ),
        )

        self.parameters.update(new_par)
        self.regenerate_callsigns()

        # Handle OWN radios information
        self.parameters["radios"] = dict()
        for r, this_radio in enumerate(self.parameters["promptlist"]):
            self.parameters["radios"][r] = {
                "name": this_radio,
                "currentfreq": self.get_rand_frequency(r),
                "targetfreq": None,
                "pos": r,
                "response_time": 0,
                "is_active": False,
                "is_prompting": False,
                "_feedbacktimer": None,
                "_feedbacktype": None,
            }
        self.lastradioselected: Optional[int] = None
        self.frequency_modulation: float = 0.1
        self.sound_path: Optional[Path] = None

        self.set_sample_sounds()

        self.automode_position: tuple[float, float] = (0.5, 0.2)

    def get_sounds_path(self) -> Path:
        return P["SOUNDS"].joinpath(self.parameters["voiceidiom"], self.parameters["voicegender"])

    def set_sample_sounds(self) -> None:
        new_path: Path = self.get_sounds_path()
        if new_path == self.sound_path:
            return

        if not new_path.exists():
            print(_("Warning: sound path %s does not exist. Check voiceidiom/voicegender combination.") % new_path)
            return

        self.sound_path = new_path
        self.samples_path: list[Path] = [
            self.sound_path.joinpath(f"{i}.wav")
            for i in [s for s in digits + ascii_lowercase]
            + [this_radio.lower() for this_radio in self.parameters["promptlist"]]
            + ["radio", "point", "frequency"]
        ]

        for sample_needed in self.samples_path:
            if not sample_needed.exists():
                print(sample_needed, _(" does not exist"))

    def regenerate_callsigns(self) -> None:
        self.parameters["owncallsign"] = self.get_callsign()
        for _i in range(self.parameters["othercallsignnumber"]):
            this_callsign: str = self.get_callsign()
            while this_callsign in [self.parameters["owncallsign"]] + self.parameters["othercallsign"]:
                this_callsign = self.get_callsign()
            self.parameters["othercallsign"].append(this_callsign)

    def create_widgets(self) -> None:
        super().create_widgets()
        self.add_widget(
            "callsign",
            Simpletext,
            container=self.task_container,
            text=_("Callsign \t\t %s") % self.parameters["owncallsign"],
            y=0.9,
        )

        active_index: int = randint(0, len(self.parameters["radios"]) - 1, self.alias, self.scenario_time)
        for pos, radio in self.parameters["radios"].items():
            radio["is_active"] = pos == active_index
            # Compute radio container
            radio_container: Container = Container(
                radio["name"],
                self.task_container.l,
                self.task_container.b + self.task_container.h * (0.7 - 0.13 * pos),
                self.task_container.w,
                self.task_container.h * 0.1,
            )

            radio["widget"] = self.add_widget(
                f"radio_{radio['name']}",
                Radio,
                container=radio_container,
                label=radio["name"],
                frequency=radio["currentfreq"],
                on=radio["is_active"],
            )

    def get_callsign(self) -> str:
        self.callsign_seed += 1
        call_rgx: str = self.parameters["callsignregex"]
        duplicateChar: bool = True
        notInList: bool = True

        self.letters = ascii_uppercase if len(self.letters) < 3 else self.letters
        self.digits = digits if len(self.digits) < 3 else self.digits

        while duplicateChar or notInList:
            callsign: str = xeger(call_rgx, self.alias, self.scenario_time, self.callsign_seed)
            duplicateChar = len(callsign) != len(set(callsign))
            notInList = any([s not in self.letters + self.digits for s in callsign])
            self.callsign_seed += 1

        for s in callsign:
            for li in [self.letters, self.digits]:
                if s in li:
                    li = li.replace(s, "")
        return callsign

    def group_audio_files(self, callsign: str, radio_name: str, freq: float) -> Any:
        list_of_sounds: list[str] = (
            ["empty"] * 20
            + [c.lower() for c in callsign]
            + [c.lower() for c in callsign]
            + ["radio"]
            + [radio_name.lower()]
            + ["frequency"]
            + [c.lower().replace(".", "point") for c in str(freq)]
            + ["empty"]
        )

        group: Any = SourceGroup()
        for f in list_of_sounds:
            source: Any = load(str(self.sound_path.joinpath(f"{f}.wav")), streaming=False)
            # print(f)
            group.add(source)
        return group

    def prompt_for_a_new_target(self, destination: str, radio_name: str) -> None:
        self.parameters["radioprompt"] = ""
        radio: dict[str, Any] = self.get_radios_by_key_value("name", radio_name)[0]
        radio_n: int = self.get_radios_number_by_key_value("name", radio_name)[0]

        callsign: str | list[str] = self.parameters[f"{destination}callsign"]
        callsign = choice(callsign, self.alias, self.scenario_time, radio_n) if isinstance(callsign, list) else callsign

        random_frequency: float = self.get_rand_frequency(radio_n)
        while not (
            self.parameters["airbandminvariationMhz"]
            < abs(random_frequency - radio["currentfreq"])
            < self.parameters["airbandmaxvariationMhz"]
        ):
            radio_n += 15
            random_frequency = self.get_rand_frequency(radio_n)

        if destination == "own":
            radio["targetfreq"] = random_frequency
            radio["is_prompting"] = True

        sound_group: Any = self.group_audio_files(callsign, radio_name, random_frequency)

        self.player: Any = Player()
        self.player.queue(sound_group)
        self.player.play()

    def get_rand_frequency(self, radio_n: int) -> float:
        return round(
            uniform(
                float(self.parameters["airbandminMhz"]),
                float(self.parameters["airbandmaxMhz"]),
                self.alias,
                self.scenario_time,
                radio_n,
            ),
            1,
        )

    def get_target_radios_list(self) -> list[dict[str, Any]]:
        # Multiple radios can have a target frequency at the same time
        # because of a potential delay in reactions
        return [r for _, r in self.parameters["radios"].items() if r["targetfreq"] is not None]

    def get_non_target_radios_list(self) -> list[dict[str, Any]]:
        # Multiple radios can have a target frequency at the same time
        # because of a potential delay in reactions
        return [r for _, r in self.parameters["radios"].items() if r["targetfreq"] is None]

    def get_active_radio_dict(self) -> Optional[dict[str, Any]]:
        radio: Optional[list[dict[str, Any]]] = self.get_radios_by_key_value("is_active", True)
        if radio is not None:
            return radio[0]

    def get_radio_dict_by_pos(self, pos: int | float) -> Optional[dict[str, Any]]:
        radio: Optional[list[dict[str, Any]]] = self.get_radios_by_key_value("pos", pos)
        if radio is not None:
            return radio[0]

    def get_radios_by_key_value(self, k: str, v: Any) -> Optional[list[dict[str, Any]]]:
        radio_list: list[dict[str, Any]] = [r for _, r in self.parameters["radios"].items() if r[k] == v]
        if len(radio_list) > 0:
            return radio_list

    def get_radios_number_by_key_value(self, k: str, v: Any) -> Optional[list[int]]:
        num_list: list[int] = [i for i, r in self.parameters["radios"].items() if r[k] == v]
        if len(num_list) > 0:
            return num_list

    def get_response_timers(self) -> list[int]:
        return [r["response_time"] for _, r in self.parameters["radios"].items() if r["response_time"] > 0]

    def get_waiting_response_radios(self) -> list[dict[str, Any]]:
        """A radio is waiting a response when it specifies a target and its prompting message
        is over"""

        return [
            r
            for _, r in self.parameters["radios"].items()
            if r in self.get_target_radios_list() and not r["is_prompting"]
        ]

    def get_max_pos(self) -> int:
        return max([r["pos"] for k, r in self.parameters["radios"].items()])

    def get_min_pos(self) -> int:
        return min([r["pos"] for k, r in self.parameters["radios"].items()])

    def modulate_frequency(self) -> None:
        if self.is_key_state(self.parameters["keys"]["tunefrequencydown"], True):
            self.get_active_radio_dict()["currentfreq"] -= self.frequency_modulation
        elif self.is_key_state(self.parameters["keys"]["tunefrequencyup"], True):
            self.get_active_radio_dict()["currentfreq"] += self.frequency_modulation

    def compute_next_plugin_state(self) -> None:
        if not super().compute_next_plugin_state():
            return

        if self.parameters["callsignregex"] != self.old_regex:
            self.regenerate_callsigns()
            self.old_regex = str(self.parameters["callsignregex"])

        self.set_sample_sounds()  # Check if sounds path has been renewed

        if self.parameters["radioprompt"].lower() in ["own", "other"]:
            radio_name_to_prompt: Optional[str] = None

            # If the prompt is relevant (own), select a radio among (available) non-target radios
            if self.parameters["radioprompt"].lower() == "own":
                non_target_radios: list[dict[str, Any]] = self.get_non_target_radios_list()
                if len(non_target_radios) > 0:
                    radio_name_to_prompt = choice(non_target_radios, self.alias, self.scenario_time, 1)["name"]
            elif self.parameters["radioprompt"].lower() == "other":
                radio_name_to_prompt = choice(self.parameters["promptlist"], self.alias, self.scenario_time, 1)

            if radio_name_to_prompt is not None:
                # If a new prompt is incoming and a prompt is still playing
                # Pause and stop this prompt
                prompting_radio_list: Optional[list[dict[str, Any]]] = self.get_radios_by_key_value("is_prompting", True)
                if prompting_radio_list is not None and len(prompting_radio_list) > 0:
                    self.player.pause()
                    del self.player
                    prompting_radio: dict[str, Any] = prompting_radio_list[0]
                    prompting_radio["is_prompting"] = False
                    self.logger.log_manual_entry(f"Target {prompting_radio['name']}:{prompting_radio['targetfreq']}")

                self.prompt_for_a_new_target(self.parameters["radioprompt"].lower(), radio_name_to_prompt)
            else:
                self.log_manual_entry("Error. Could not trigger prompt", key="manual")

        if self.can_receive_keys:
            self.modulate_frequency()

        # If a target is defined + auditory prompt has ended
        # response can occur, so increment response_time
        target_radios: list[dict[str, Any]] = self.get_target_radios_list()
        active: dict[str, Any] = self.get_active_radio_dict()

        # Browse targeted radios
        for radio in target_radios:
            # Increment response time as soon as auditory prompting has ended
            if not radio["is_prompting"]:
                radio["response_time"] += self.parameters["taskupdatetime"]

                # Record potential target miss
                if radio["response_time"] >= self.parameters["maxresponsedelay"]:
                    self.record_target_missing(radio)

            elif self.player.source is None:  # If the radio prompt has just ended
                radio["is_prompting"] = False
                self.logger.log_manual_entry(f"Target {radio['name']}:{radio['targetfreq']}")

        # If multiple radios must be modified
        # The automatic solver sticks to the first one (until it is tuned)
        if self.parameters["automaticsolver"] is True and not REPLAY_MODE:
            waiting_radios: list[dict[str, Any]] = self.get_waiting_response_radios()

            # Only if a radio is waiting autosolving, do it
            if len(waiting_radios) > 0:
                autoradio: dict[str, Any] = waiting_radios[0]

                if active != autoradio:  # Automatic radio switch if needed
                    active["is_active"] = False
                    current_index: int = active["pos"]
                    target_index: int = autoradio["pos"]
                    new_index: float = current_index + copysign(1, target_index - current_index)
                    self.get_radio_dict_by_pos(new_index)["is_active"] = True

                # Automatic radio tune
                elif active["targetfreq"] != active["currentfreq"]:
                    active["currentfreq"] = round(
                        active["currentfreq"] + copysign(0.1, active["targetfreq"] - active["currentfreq"]), 1
                    )
                else:
                    self.confirm_response()  # Emulate a response confirmation

        active["currentfreq"] = self.keep_value_between(
            active["currentfreq"], up=self.parameters["airbandmaxMhz"], down=self.parameters["airbandminMhz"]
        )

        # Feedback handling
        for _r, radio in self.parameters["radios"].items():
            if radio["_feedbacktimer"] is not None:
                radio["_feedbacktimer"] -= self.parameters["taskupdatetime"]
                if radio["_feedbacktimer"] <= 0:
                    radio["_feedbacktimer"] = None
                    radio["_feedbacktype"] = None

    def refresh_widgets(self) -> None:
        if not super().refresh_widgets():
            return

        self.widgets["communications_callsign"].set_text(self.parameters["owncallsign"])

        # Move arrow to active radio
        for _, radio in self.parameters["radios"].items():
            if not radio["is_active"] and radio["widget"].is_selected:
                radio["widget"].hide_arrows()
            elif radio["is_active"] and not radio["widget"].is_selected:
                radio["widget"].show_arrows()

            # Propagate current frequencies values to the widgets
            radio["widget"].set_frequency_text(radio["currentfreq"])

            # ... also check a need for feedback refreshing
            if radio["_feedbacktimer"] is not None:
                color: tuple[int, ...] = self.parameters["feedbacks"][radio["_feedbacktype"]]["color"]
            else:
                color = C["BACKGROUND"]
            radio["widget"].set_feedback_color(color)

    def disable_radio_target(self, radio: dict[str, Any]) -> None:
        radio["response_time"] = 0
        radio["targetfreq"] = None

    def record_target_missing(self, target_radio: dict[str, Any]) -> None:
        self.log_performance("target_radio", target_radio["name"])
        self.log_performance("target_frequency", target_radio["targetfreq"])
        self.log_performance("response_was_needed", True)
        self.log_performance("responded_radio", float("nan"))
        self.log_performance("responded_frequency", float("nan"))
        self.log_performance("correct_radio", False)
        self.log_performance("response_deviation", float("nan"))
        self.log_performance("response_time", float("nan"))
        self.log_performance("sdt_value", "MISS")

        self.disable_radio_target(target_radio)

        self.set_feedback(target_radio, ft="negative")

    def get_sdt_value(self, response_needed: bool, was_a_radio_responded: bool, correct_radio: bool | float, response_deviation: float) -> Optional[str]:
        if not response_needed:
            return "FA"
        elif was_a_radio_responded is False:
            return "MISS"
        elif correct_radio and response_deviation == 0:
            return "HIT"
        elif correct_radio is False and response_deviation == 0:
            return "BAD_RADIO"
        elif response_deviation != 0 and correct_radio:
            return "BAD_FREQ"
        elif correct_radio is False and response_deviation != 0:
            return "BAD_RADIO_FREQ"

    def confirm_response(self) -> None:
        """Evaluate response performance and log it"""

        # Retrieve the responded radio and the target radios
        responded_radio: dict[str, Any] = self.get_active_radio_dict()
        waiting_radios: list[dict[str, Any]] = self.get_waiting_response_radios()

        # Check if there was a target to be responded to
        response_needed: bool = len(waiting_radios) > 0

        # Check if the responded radio was prompting (good radio)
        good_radio: bool | float = responded_radio in waiting_radios if len(waiting_radios) else float("nan")

        # If a target radio is responded, get it to compute response deviation and time
        # If not, get the target radio only if it is single
        # (if there were two target radios simultaneously, we can't decide which to select
        #  to compute deviation and response time with the uncorrect responded radio)
        measure_radio: Optional[dict[str, Any]]
        if responded_radio in waiting_radios:
            measure_radio = responded_radio
        elif len(waiting_radios) == 1:
            measure_radio = waiting_radios[0]
        else:
            measure_radio = None

        # Now compute
        deviation: float
        rt: int | float
        target_frequency: float | None
        target_radio_name: str | float
        if measure_radio is not None:
            target_frequency = measure_radio["targetfreq"]
            target_radio_name = measure_radio["name"]
            deviation = round(responded_radio["currentfreq"] - target_frequency, 1)
            rt = measure_radio["response_time"]
        else:
            deviation = rt = target_frequency = target_radio_name = float("nan")

        sdt: Optional[str] = self.get_sdt_value(response_needed, True, good_radio, deviation)

        self.log_performance("response_was_needed", response_needed)
        self.log_performance("target_radio", target_radio_name)
        self.log_performance("responded_radio", responded_radio["name"])
        self.log_performance("target_frequency", target_frequency)
        self.log_performance("responded_frequency", responded_radio["currentfreq"])
        self.log_performance("correct_radio", good_radio)
        self.log_performance("response_deviation", deviation)
        self.log_performance("response_time", rt)
        self.log_performance("sdt_value", sdt)

        # Response is good if both radio and frequency are correct
        if not response_needed:
            self.set_feedback(responded_radio, ft="negative")
        else:
            if good_radio and deviation == 0:
                self.disable_radio_target(responded_radio)
                self.set_feedback(responded_radio, ft="positive")
            else:
                self.set_feedback(responded_radio, ft="negative")

    def set_feedback(self, radio: dict[str, Any], ft: str) -> None:
        # Set the feedback type and duration, if the gauge has got one
        # (the feedback widget is refreshed by the refresh_widget method)
        if self.parameters["feedbacks"][ft]["active"]:
            radio["_feedbacktype"] = ft
            radio["_feedbacktimer"] = self.parameters["feedbackduration"]

    def do_on_key(self, key: str, state: str, emulate: bool) -> None:
        """Check for radio change and frequency validation"""
        key = super().do_on_key(key, state, emulate)
        if key is None:
            return

        if state == "press":
            change_radio: int = 0
            if key == self.parameters["keys"]["selectradioup"]:
                change_radio = -1
            elif key == self.parameters["keys"]["selectradiodown"]:
                change_radio = 1

            if change_radio != 0:
                next_active_n: int | float = self.keep_value_between(
                    self.get_active_radio_dict()["pos"] + change_radio, down=self.get_min_pos(), up=self.get_max_pos()
                )

                self.get_active_radio_dict()["is_active"] = False
                self.get_radio_dict_by_pos(next_active_n)["is_active"] = True

            elif key == self.parameters["keys"]["validateresponse"]:
                self.confirm_response()
