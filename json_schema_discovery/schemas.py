import copy
from abc import ABC, abstractmethod


class Schema(ABC):

    """Base class for mergable schemas"""

    @abstractmethod
    def _merge(self, other):
        ...

    @abstractmethod
    def _iter_strings(self, indent=1, show_counts=True):
        """Iterate over the lines of the long string representation"""
        ...

    @property
    @abstractmethod
    def count(self):
        ...

    @property
    @abstractmethod
    def short_type_str(self):
        ...

    def _iter_statistics(self, depth=1):
        return []

    def _iter_sub_statistics(self, depth=1):
        for key, *info in self._iter_statistics(depth=depth - 1):
            yield (f"    {key}", *info)

    def __iadd__(self, other):
        if not isinstance(other, Schema):
            try:
                other = make_schema(other)
            except ValueError:
                return NotImplemented
        return self._merge(other)

    def __str__(self):
        return "\n".join(self._iter_strings(indent=1, show_counts=True))


class CountableSchema(Schema):

    """
    Schemas where direct occurence counting makes sense,

    For instance Empty and Variant are not countable since they do not reflect actual json structures
    """

    def __init__(self):
        self._count = 1

    @property
    def count(self):
        return self._count

    def add_counts(self, other):
        if isinstance(other, CountableSchema):
            self._count += other._count


class Empty(Schema):

    """
    The empty structure, to be understood as "no schema can be inferred for now"

    Used for instance as the internal type of an empty list
    Does NOT represent a null, that whould be a Value object where value.type == NoneType instead
    """

    def __hash__(self):
        return hash(None)

    def __eq__(self, other):
        return isinstance(other, Empty)

    def __bool__(self):
        return False

    @property
    def count(self):
        return 0

    def _merge(self, other):
        return copy.copy(other)

    def _iter_strings(self, indent=1, show_counts=True):
        yield "<empty>"

    @property
    def short_type_str(self):
        return str(self)


class Value(CountableSchema):

    """
    Scalar Json value, either a number (int or float), a string, a boolean or null (None)
    """

    def __init__(self, value):
        super().__init__()
        self.value = value
        self.type = type(value)

    def __hash__(self):
        return hash(self.type)

    def __eq__(self, other):
        if isinstance(other, Value):
            return self.type == other.type
        else:
            return False

    def __bool__(self):
        return True

    def _merge(self, other):
        if self != other:
            return Variant((self, other))
        else:
            self.add_counts(other)
            return self

    def _iter_strings(self, indent=1, show_counts=True):
        yield _count(self, show_counts) + self.type.__name__

    @property
    def short_type_str(self):
        return self.type.__name__


class DictStructure(CountableSchema):

    """
    JSON Object structure

    Stores a dict mapping keys to substructures
    The internal structure dictionnary is proxied to enable direct acces to substructures by indexing
    """

    def __init__(self, _dict):
        for key in _dict.keys():
            if not isinstance(key, str):
                raise TypeError(f"Invalid type for key {key} : {type(key).__name__}")

        super().__init__()
        self.keys = {key: make_schema(value) for key, value in _dict.items()}

    def __hash__(self):
        sub_dict = {key: hash(value) for key, value in self.keys.items()}
        return hash(frozenset(tuple(sorted(sub_dict.items()))))

    def __eq__(self, other):
        if isinstance(other, DictStructure):
            return self.keys == other.keys
        else:
            return False

    def __getitem__(self, key):
        return self.keys[key]

    def __setitem__(self, key, value):
        self.keys[key] = make_schema(value)

    def __bool__(self):
        return bool(self.keys)

    def _merge(self, other):
        if not isinstance(other, DictStructure):
            return Variant((self, other))
        else:
            res = copy.copy(self)
            res.add_counts(other)
            # merge each common key
            for key in res.keys.keys() & other.keys.keys():
                res[key] += other[key]
            # add each new key
            for key in other.keys.keys() - res.keys.keys():
                res[key] = copy.copy(other[key])
            return res

    def _iter_strings(self, indent=1, show_counts=True):
        if not (self):
            yield _count(self, show_counts) + "{}"
        else:
            yield _count(self, show_counts) + "{"
            for key in sorted(self.keys):
                lines = self[key]._iter_strings(indent=indent, show_counts=show_counts)
                yield " " * indent + f"{key} : {next(lines)}"
                line = next(lines, None)
                for next_line in lines:
                    yield " " * indent * 2 + line
                    line = next_line
                if line is not None:
                    yield " " * indent + line
            yield "}"

    def _iter_statistics(self, depth=1):

        if depth <= 0:
            return

        for key, value in DictStructure.statistic_sorting(self.keys):
            yield key, value.short_type_str, value.count, value.count / self.count * 100
            yield from value._iter_sub_statistics(depth=depth)

    @staticmethod
    def statistic_sorting(_dict):
        return sorted(_dict.items(), key=lambda x: (-x[1].count, x[0]))

    @property
    def short_type_str(self):
        return "dict"


class ListStructure(CountableSchema):

    """
    JSON Array structure

    Stores the merged structure of the array's elements
    """

    def __init__(self, _list):
        super().__init__()
        self.element_schema = Empty()
        for element in _list:
            self.element_schema += make_schema(element)

    def __hash__(self):
        return hash((list, hash(self.element_schema)))

    def __eq__(self, other):
        if isinstance(other, ListStructure):
            return self.element_schema == other.element_schema
        else:
            return False

    def __bool__(self):
        return bool(self.element_schema)

    def _merge(self, other):
        if not isinstance(other, ListStructure):
            return Variant((self, other))
        else:
            res = copy.copy(self)
            res.add_counts(other)
            res.element_schema += other.element_schema
            return res

    def _iter_strings(self, indent=1, show_counts=True):
        if not (self):
            yield _count(self, show_counts) + "[]"
        else:
            yield "["
            for line in self.element_schema._iter_strings(
                indent=indent, show_counts=show_counts
            ):
                yield " " * indent + line
            yield "]"

    def _iter_statistics(self, depth=1):

        if depth <= 0:
            return

        yield f"[{self.element_schema.count}]", self.element_schema.short_type_str
        yield from self.element_schema._iter_sub_statistics(depth=depth)

    def _iter_sub_statistics(self, depth=1):
        if depth <= 0:
            return
        for key, *info in self._iter_statistics(depth=depth - 1):
            yield (f"    {key}", *info)

    @property
    def short_type_str(self):
        return "list"


class Variant(Schema):

    """
    Represents an alternative between otherwise non-mergable structures

    Keeps a collection of scalar types, one merged object structure, and one merged list structure
    """

    def __init__(self, objects):
        self.values = dict()
        self.dicts = Empty()
        self.lists = Empty()

        for obj in map(make_schema, objects):
            self._merge(obj)

    def __hash__(self):
        return hash(
            (
                frozenset(hash(x) for x in self.values),
                hash(self.dicts),
                hash(self.lists),
            )
        )

    def __eq__(self, other):
        if isinstance(other, Variant):
            return (
                self.value == other.values
                and self.dicts == other.dicts
                and self.lists == other.lists
            )
        else:
            return False

    def __bool__(self):
        return any((self.values, self.dicts, self.lists))

    def __iter__(self):
        yield from self.values.values()
        if self.dicts != Empty():
            yield self.dicts
        if self.lists != Empty():
            yield self.lists

    @property
    def count(self):
        return sum(x.count for x in self)

    def _merge(self, other):
        if isinstance(other, Empty):
            pass
        elif isinstance(other, Value):
            if other.type in self.values:
                self.values[other.type] += other
            else:
                self.values[other.type] = other
        elif isinstance(other, ListStructure):
            self.lists += other
        elif isinstance(other, DictStructure):
            self.dicts += other
        elif isinstance(other, Variant):
            # merge common types
            for _type in self.values.keys() & other.values.keys():
                self.values[_type] += other.values[_type]
            # add new types
            for _type in other.values.keys() - self.values.keys():
                self.values[_type] = other.values[_type]
            self.dicts += other.dicts
            self.lists += other.dicts
        return self

    def _iter_strings(self, indent=1, show_counts=True):
        if not (self):
            yield _count(self, show_counts) + "Variant()"
        elif self.values and (self.dicts == self.lists == Empty()):
            yield _count(
                self, show_counts
            ) + f'Variant({", ".join(dumps(x) for x in self.values.values())})'
        else:
            yield _count(self, show_counts) + "Variant("
            for value in self:
                for line in value._iter_strings(indent=indent, show_counts=show_counts):
                    yield " " * indent + line
            yield ")"

    def _iter_statistics(self, depth=1):

        if depth <= 0:
            return
        for schema in self:
            yield f"<{schema.short_type_str}>", schema.short_type_str, schema.count, schema.count / self.count * 100
            yield from schema._iter_sub_statistics(depth=depth)

    @property
    def short_type_str(self):
        return f'Variant({", ".join(x.short_type_str for x in self)})'


def make_schema(obj):
    """
    Create a schema from a json-like object

    Factory method that passes the object to the right class constructor
    Send the object back if it's already a schema
    """

    if not isinstance(obj, Schema):
        if isinstance(obj, dict):
            return DictStructure(obj)
        elif isinstance(obj, list):
            return ListStructure(obj)
        elif isinstance(obj, (int, float, str, bool)) or (obj is None):
            return Value(obj)
        else:
            raise ValueError(f"object {obj} cannot be represented as a JSON Structure")
    else:
        return obj


def _count(s, show_counts=True):
    res = ""
    if show_counts:
        res += f"{s.count}×"
    return res
