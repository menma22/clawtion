"""clawtion CLI interface package.

Entry point: ``clawtion.interfaces.cli.main:main``
"""

from clawtion.interfaces.cli.main import main, async_cmd, set_verbose, is_verbose
from clawtion.interfaces.cli.init import init
from clawtion.interfaces.cli.service import service
from clawtion.interfaces.cli.index import index
from clawtion.interfaces.cli.search import search
from clawtion.interfaces.cli.note import note
from clawtion.interfaces.cli.trash import trash
from clawtion.interfaces.cli.doctor import doctor
from clawtion.interfaces.cli.config import config_cmd

__all__ = [
    "main",
    "async_cmd",
    "set_verbose",
    "is_verbose",
    "init",
    "service",
    "index",
    "search",
    "note",
    "trash",
    "doctor",
    "config_cmd",
]
