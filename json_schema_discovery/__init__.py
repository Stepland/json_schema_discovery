from .schemas import *


def dumps(s: Mergeable, indent=1, show_counts=True):
    """Dump structure as a string"""
    return "\n".join(s._iter_strings(indent=indent, show_counts=show_counts))


def statistics(d: DictStructure):
    """Get the frequencies of first level keys of a DictStructure"""
    counts = list(d.keys.items())
    counts.sort(key=lambda x: (-x[1].count, x[0]))
    name_length = max(len(x[0]) for x in counts)
    for key, value in counts:
        print(f"{key:<{name_length}} : {value.count/d.count*100:7.3f} %")
