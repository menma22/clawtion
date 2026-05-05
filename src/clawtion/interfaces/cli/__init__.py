"""clawtion CLI interface package.

Entry point: ``clawtion.interfaces.cli.main:main``
"""

from clawtion.interfaces.cli.config import config_cmd
from clawtion.interfaces.cli.doctor import doctor
from clawtion.interfaces.cli.git_cmd import git as git_group
from clawtion.interfaces.cli.index import index
from clawtion.interfaces.cli.init import init
from clawtion.interfaces.cli.main import main
from clawtion.interfaces.cli.note import note
from clawtion.interfaces.cli.search import search
from clawtion.interfaces.cli.service import service
from clawtion.interfaces.cli.trash import trash
from clawtion.utils.async_helpers import async_cmd, is_verbose, set_verbose

__all__ = [
    "async_cmd",
    "config_cmd",
    "doctor",
    "git_group",
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
