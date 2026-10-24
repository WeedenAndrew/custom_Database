"""Formerly HELD-OUT (never shown to either agent during the rounds; added here after both).  acceptance suite for custom-database-structures (hashes, lists,
one type per key). Written from the spec only; never shown to either agent."""
import pytest

from acceptance_common import Clock, ns, run
from custom_database import Cache

BIG = 2**70


# --- hashes
def test_hash_set_get_all_keys_del():
    c = Cache(ns())
    assert run(c.hset("h", "b", 1)) is True and run(c.hset("h", "a", BIG)) is True
    assert run(c.hset("h", "b", 1.0)) is False
    got = run(c.hgetall("h"))
    assert got == {"a": BIG, "b": 1.0} and type(got["a"]) is int and type(got["b"]) is float
    assert run(c.hget("h", "a")) == BIG and run(c.hget("h", "zz")) is None and run(c.hget("nope", "a")) is None
    assert run(c.hkeys("h")) == ["a", "b"] and run(c.hkeys("nope")) == [] and run(c.hgetall("nope")) == {}
    assert run(c.hdel("h", "a", "zz", "a")) == 1


def test_emptied_hash_deletes_key_and_its_expiry():
    clk = Clock(); c = Cache(ns(), clock=clk)
    run(c.hset("h", "f", True)); run(c.expire("h", 50))
    assert run(c.hdel("h", "f")) == 1
    assert "h" not in run(c.keys()) and run(c.ttl("h")) == -2.0
    run(c.hset("h", "g", 1))
    assert run(c.ttl("h")) == -1.0                      # the old expiry did not come back


# --- lists
def test_list_push_order_pop_len_range():
    c = Cache(ns())
    assert run(c.lpush("l", 1, 2)) == 2                 # [2, 1], as in Redis
    assert run(c.rpush("l", 3, 4.0)) == 4               # [2, 1, 3, 4.0]
    assert run(c.lrange("l", 0, -1)) == [2, 1, 3, 4.0]
    assert type(run(c.lrange("l", -1, -1))[0]) is float
    assert run(c.lrange("l", 1, 2)) == [1, 3] and run(c.lrange("l", -2, 100)) == [3, 4.0]
    assert run(c.lrange("l", 3, 1)) == [] and run(c.lrange("l", 10, 20)) == [] and run(c.lrange("l", -100, 0)) == [2]
    assert run(c.llen("l")) == 4 and run(c.llen("nope")) == 0 and run(c.lrange("nope", 0, -1)) == []
    assert run(c.lpop("l")) == 2 and run(c.rpop("l")) == 4.0 and run(c.lrange("l", 0, -1)) == [1, 3]
    assert run(c.lpop("nope")) is None and run(c.rpop("nope")) is None


def test_emptied_list_deletes_key():
    c = Cache(ns()); run(c.rpush("l", "x"))
    assert run(c.rpop("l")) == "x" and run(c.keys()) == [] and run(c.ttl("l")) == -2.0


def test_expiry_covers_a_whole_list_and_hash():
    clk = Clock(); c = Cache(ns(), clock=clk)
    run(c.rpush("l", 1, 2)); run(c.hset("h", "f", 1))
    run(c.expire("l", 5)); run(c.expire("h", 5))
    clk.t += 6
    assert run(c.llen("l")) == 0 and run(c.hgetall("h")) == {} and run(c.keys()) == []


# --- one type per key
def test_wrong_type_raises_and_changes_nothing():
    c = Cache(ns())
    run(c.set("v", 1)); run(c.hset("h", "f", 1)); run(c.rpush("l", 1))
    wrong = [lambda: c.get("h"), lambda: c.incr("h"), lambda: c.rpush("h", 1), lambda: c.llen("h"),
             lambda: c.get("l"), lambda: c.incr("l"), lambda: c.hset("l", "f", 1), lambda: c.hgetall("l"),
             lambda: c.hget("v", "f"), lambda: c.hkeys("v"), lambda: c.lpush("v", 1), lambda: c.lpop("v"),
             lambda: c.lrange("v", 0, -1)]
    for call in wrong:
        with pytest.raises(ValueError):
            run(call())
    assert run(c.get("v")) == 1 and run(c.hgetall("h")) == {"f": 1} and run(c.lrange("l", 0, -1)) == [1]


def test_set_replaces_a_hash_or_list_and_delete_works_on_all_kinds():
    c = Cache(ns()); run(c.hset("h", "f", 1)); run(c.rpush("l", 1))
    run(c.set("h", "now a value"))
    assert run(c.get("h")) == "now a value"
    assert run(c.delete("l")) is True and run(c.llen("l")) == 0
    assert sorted(run(c.keys())) == ["h"]


# --- isolation still holds for structures
def test_structures_are_isolated_between_namespaces():
    a, b = Cache(ns("a")), Cache(ns("b"))
    run(a.hset("h", "f", "A")); run(a.rpush("l", "A"))
    assert run(b.hgetall("h")) == {} and run(b.llen("l")) == 0 and run(b.keys()) == []


# --- errors
@pytest.mark.parametrize("call", ["hdel_none", "lpush_none", "rpush_none", "lrange_float", "lrange_bool",
                                  "field_empty", "field_long", "field_int", "hash_value_none", "list_value_tuple"])
def test_structure_errors(call):
    c = Cache(ns())
    run(c.hset("h", "f", 1)); run(c.rpush("l", 1))
    calls = {"hdel_none": lambda: c.hdel("h"), "lpush_none": lambda: c.lpush("l"), "rpush_none": lambda: c.rpush("l"),
             "lrange_float": lambda: c.lrange("l", 0.0, 1), "lrange_bool": lambda: c.lrange("l", 0, True),
             "field_empty": lambda: c.hset("h", "", 1), "field_long": lambda: c.hset("h", "f" * 513, 1),
             "field_int": lambda: c.hget("h", 5), "hash_value_none": lambda: c.hset("h", "g", None),
             "list_value_tuple": lambda: c.rpush("l", (1,))}
    with pytest.raises(ValueError):
        run(calls[call]())
    assert run(c.hgetall("h")) == {"f": 1} and run(c.lrange("l", 0, -1)) == [1]


def test_keys_skips_an_expired_hash_and_list_with_no_read_first():
    clk = Clock(); c = Cache(ns(), clock=clk)
    run(c.hset("h", "f", 1)); run(c.rpush("l", 1)); run(c.set("v", 1))
    run(c.expire("h", 1)); run(c.expire("l", 1))
    clk.t += 2
    assert run(c.keys()) == ["v"]
