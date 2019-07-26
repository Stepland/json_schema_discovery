import random

from json_schema_discovery import make_schema, Empty, DictStructure, ListStructure


def test_merge_dict():

    count_a = random.randint(1, 100)
    count_b = random.randint(1, 100)

    schema_a = Empty()
    schema_b = Empty()

    for _ in range(count_a):
        schema_a += {"key": random.randint(0, 100)}
    for _ in range(count_b):
        schema_b += {"key": random.randint(0, 100)}

    assert isinstance(schema_a, DictStructure)
    assert isinstance(schema_b, DictStructure)
    assert schema_a["key"].count == count_a
    assert schema_b["key"].count == count_b

    schema_a += schema_b

    assert type(schema_a) == DictStructure
    assert schema_a["key"].count == count_a + count_b


def test_merge_dict_list():

    lists = []
    for _ in range(random.randint(5, 10)):
        lists.append([{"key": random.random()}] * random.randint(5, 10))

    schema = Empty()
    for obj in lists:
        schema += obj

    assert isinstance(schema, ListStructure)
    assert isinstance(schema.element_schema, DictStructure)
    assert schema.element_schema["key"].count == sum(len(x) for x in lists)
