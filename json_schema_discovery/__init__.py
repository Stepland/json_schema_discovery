"""
Database-agnostic JSON schema discovery

Create and merge json schemas, with occurence counting
"""

from .schemas import *
import tabulate

tabulate.PRESERVE_WHITESPACE = True


def dumps(s: Schema, indent=1, show_counts=True):
    """Dump structure as a string"""
    return "\n".join(s._iter_strings(indent=indent, show_counts=show_counts))


def statistics(s: Schema, **kwargs):
    """Get some statistics regarding type and frequencies of keys"""

    print(
        tabulate.tabulate(
            list(s._iter_statistics(**kwargs)),
            headers=["path", "type", "occurences", "%"],
            floatfmt=".3f",
        )
    )
