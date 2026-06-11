"""Minimal real-corpus script fixture."""

import sims4.commands
import sims4communitylib.utils as s4cl_utils
from sims4.utils import inject_to

COMMAND_MODULE = sims4.commands.__name__
S4CL_MODULE = s4cl_utils.__name__


class FixtureTarget:
    def method(self):
        return COMMAND_MODULE, S4CL_MODULE


@inject_to(FixtureTarget, "method")
def probe_injection(original, self, *args, **kwargs):
    if args or kwargs:
        return original(self, *args, **kwargs)
    return original(self)
