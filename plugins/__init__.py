# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from importlib import import_module

from .abstractplugin import AbstractPlugin  # noqa: F401


def _build_missing_dependency_plugin(class_name, error):
	class MissingDependencyPlugin(AbstractPlugin):
		def __init__(self, *args, **kwargs):
			raise ModuleNotFoundError(
				f"{class_name} is unavailable because an optional dependency could not be imported: {error}"
			) from error

	MissingDependencyPlugin.__name__ = class_name
	return MissingDependencyPlugin


def _load_plugin(module_name, class_name):
	try:
		module = import_module(f".{module_name}", __name__)
		globals()[class_name] = getattr(module, class_name)
	except ModuleNotFoundError as error:
		globals()[class_name] = _build_missing_dependency_plugin(class_name, error)


_load_plugin("communications", "Communications")
_load_plugin("facecamera", "Facecamera")
_load_plugin("genericscales", "Genericscales")
_load_plugin("generictrigger", "Generictrigger")
_load_plugin("instructions", "Instructions")
_load_plugin("labstreaminglayer", "Labstreaminglayer")
_load_plugin("parallelport", "Parallelport")
_load_plugin("performance", "Performance")
_load_plugin("resman", "Resman")
_load_plugin("scheduling", "Scheduling")
_load_plugin("sysmon", "Sysmon")
_load_plugin("track", "Track")
