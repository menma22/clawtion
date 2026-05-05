"""clawtion CLI interface package.

Entry point: ``clawtion.interfaces.cli.main:main``
"""

from clawtion.interfaces.cli.config import config_cmd
from clawtion.interfaces.cli.doctor import doctor
from clawtion.interfaces.cli.index import index
from clawtion.interfaces.cli.init import init
from clawtion.interfaces.cli.main import async_cmd, is_verbose, main, set_verbose
from clawtion.interfaces.cli.note import note
from clawtion.interfaces.cli.search import search
from clawtion.interfaces.cli.service import service
from clawtion.interfaces.cli.trash import trash

__all__ = [
    "async_cmd",
    "config_cmd",
    "doctor",
    "index",
    "init",
    "is_verbose",
    "main",
    "note",
    "search",
    "service",
    "set_verbose",
    "trash",
]
