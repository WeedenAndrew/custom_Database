"""Formerly HELD-OUT (never shown to either agent during the rounds; added here after both).  acceptance suite for custom-database-core. Written from the spec
only; never shown to the builder or the tester. custom_Database DoD box 4."""
import math

import pytest

from acceptance_common import Clock, ns, run
from custom_database import Cache

BIG = 2**63 + 12345


# --- exact types
@pytest.mark.parametrize("v", ["s", 0, -7, BIG, 1.0, 2.5, True, False, [], {}, [1, 1.0, True, "x"],
                               {"a": {"b": [1, {"c": BIG}]}, "n": 3}])
def test_exact_type_round_trip(v):
    c = Cache(ns())
    run(c.set("k", v))
    got = run(c.get("k"))
    assert got == v and type(got) is type(v)
    if isinstance(v, (list, dict)):
        assert repr(got) == repr(v)          # nested types kept too (1 stays int, 1.0 stays float, True stays bool)


def test_missing_key_is_none():
    assert run(Cache(ns()).get("nope")) is None


def test_set_replaces_and_may_change_type():
    c = Cache(ns()); run(c.set("k", 1)); run(c.set("k", "one"))
    assert run(c.get("k")) == "one"


# --- expiry, on an injected clock
def test_ttl_expiry_and_conventions():
    clk = Clock(); c = Cache(ns(), clock=clk)
    run(c.set("a", 1, ttl=10)); run(c.set("b", 2))
    assert run(c.ttl("b")) == -1.0 and run(c.ttl("zzz")) == -2.0
    assert math.isclose(run(c.ttl("a")), 10.0)
    clk.t += 9.5
    assert run(c.get("a")) == 1 and math.isclose(run(c.ttl("a")), 0.5)
    clk.t += 1
    assert run(c.get("a")) is None and run(c.ttl("a")) == -2.0
    assert run(c.keys()) == ["b"] and run(c.delete("a")) is False


def test_keys_skips_expired_keys_with_no_read_first():
    # added after the planted-mistake check: every earlier keys() check read the expired
    # key first, which lets an implementation that deletes-on-read hide a keys() bug
    clk = Clock(); c = Cache(ns(), clock=clk)
    run(c.set("gone", 1, ttl=1)); run(c.set("pre:gone", 1, ttl=1)); run(c.set("stay", 2)); run(c.set("pre:stay", 2))
    clk.t += 2
    assert run(c.keys()) == ["pre:stay", "stay"]
    assert run(c.keys("pre:")) == ["pre:stay"]


def test_set_without_ttl_clears_expiry():
    clk = Clock(); c = Cache(ns(), clock=clk)
    run(c.set("k", 1, ttl=5)); run(c.set("k", 2))
    clk.t += 100
    assert run(c.get("k")) == 2 and run(c.ttl("k")) == -1.0


def test_expire_on_live_and_missing():
    clk = Clock(); c = Cache(ns(), clock=clk)
    run(c.set("k", "v"))
    assert run(c.expire("k", 3)) is True and run(c.expire("missing", 3)) is False
    clk.t += 3.01
    assert run(c.get("k")) is None


# --- incr
def test_incr_counts_from_zero_and_keeps_expiry():
    clk = Clock(); c = Cache(ns(), clock=clk)
    assert run(c.incr("n")) == 1 and run(c.incr("n", 5)) == 6 and run(c.incr("n", -10)) == -4
    assert run(c.ttl("n")) == -1.0
    run(c.set("m", 1, ttl=10)); run(c.incr("m"))
    assert run(c.get("m")) == 2 and math.isclose(run(c.ttl("m")), 10.0)
    clk.t += 11
    assert run(c.incr("m")) == 1 and run(c.ttl("m")) == -1.0   # expired counts as 0, no expiry


@pytest.mark.parametrize("stored", ["1", 1.5, True, [1]])
def test_incr_on_a_non_int_raises_and_changes_nothing(stored):
    c = Cache(ns()); run(c.set("k", stored))
    with pytest.raises(ValueError):
        run(c.incr("k"))
    assert run(c.get("k")) == stored


@pytest.mark.parametrize("by", [1.0, "1", True, None])
def test_incr_by_must_be_int(by):
    with pytest.raises(ValueError):
        run(Cache(ns()).incr("k", by))


# --- delete, keys
def test_delete_and_keys_sorted_with_prefix():
    c = Cache(ns())
    for k in ["b", "a", "ab", "c:1", "c:2"]:
        run(c.set(k, 1))
    assert run(c.keys()) == ["a", "ab", "b", "c:1", "c:2"]
    assert run(c.keys("a")) == ["a", "ab"] and run(c.keys("c:")) == ["c:1", "c:2"] and run(c.keys("zz")) == []
    assert run(c.delete("a")) is True and run(c.delete("a")) is False
    assert run(c.keys("a")) == ["ab"]


@pytest.mark.parametrize("key", ["with:colon", "a/b", "sp ace", "ünïcødé ✓", ".", "..", "cdb.x", "-", "_", "0" * 512])
def test_any_characters_in_keys(key):
    c = Cache(ns()); run(c.set(key, key))
    assert run(c.get(key)) == key and key in run(c.keys())


# --- isolation (Andrew's requirement)
def test_namespaces_never_collide_even_with_separator_tricks():
    base = ns("iso")
    pairs = [(base + "a", "b:c"), (base + "a:b", "c"), (base + "a.b", "c"), (base + "a", "b.c"),
             (base + "a", "b"), (base + "ab", ""), (base + "a" + "6", "2")]
    pairs = [(n, k) for n, k in pairs if k]
    for i, (n, k) in enumerate(pairs):
        run(Cache(n).set(k, i))
    for i, (n, k) in enumerate(pairs):
        assert run(Cache(n).get(k)) == i, (n, k)


def test_no_peeking_keys_lists_only_own_namespace():
    a, b = Cache(ns("a")), Cache(ns("b"))
    run(a.set("secret", "A")); run(b.set("other", "B"))
    assert run(a.keys()) == ["secret"] and run(b.keys()) == ["other"]
    assert run(b.get("secret")) is None and run(b.delete("secret")) is False
    assert run(a.get("secret")) == "A"


def test_two_handles_on_one_namespace_share_data():
    n = ns(); run(Cache(n).set("k", 1))
    assert run(Cache(n).get("k")) == 1


def test_a_namespace_that_prefixes_another_does_not_see_it():
    base = ns("p")
    run(Cache(base + "x").set("k", 1))
    assert run(Cache(base).keys()) == [] and run(Cache(base).get("xk")) is None


# --- errors: raise ValueError, write nothing
@pytest.mark.parametrize("bad", ["", 5, None, "x" * 129])
def test_bad_namespace(bad):
    with pytest.raises(ValueError):
        Cache(bad)


@pytest.mark.parametrize("bad", ["", 5, None, "k" * 513])
def test_bad_key(bad):
    c = Cache(ns())
    for call in (lambda: c.get(bad), lambda: c.set(bad, 1), lambda: c.delete(bad), lambda: c.incr(bad),
                 lambda: c.expire(bad, 1), lambda: c.ttl(bad)):
        with pytest.raises(ValueError):
            run(call())


def test_bad_prefix():
    with pytest.raises(ValueError):
        run(Cache(ns()).keys(5))


@pytest.mark.parametrize("bad", [None, (1, 2), {1, 2}, b"x", {1: "a"}, [1, None], {"a": None}, float("nan"),
                                 float("inf"), object()])
def test_bad_values_raise_and_write_nothing(bad):
    c = Cache(ns())
    with pytest.raises(ValueError):
        run(c.set("k", bad))
    assert run(c.get("k")) is None and run(c.keys()) == []


@pytest.mark.parametrize("bad", [0, -1, -0.5, True, "5", None])
def test_bad_ttl_raises_and_writes_nothing(bad):
    c = Cache(ns())
    if bad is None:
        run(c.set("k", 1, ttl=None)); assert run(c.ttl("k")) == -1.0; return   # None means no expiry
    with pytest.raises(ValueError):
        run(c.set("k", 1, ttl=bad))
    assert run(c.get("k")) is None
    run(c.set("j", 1))
    with pytest.raises(ValueError):
        run(c.expire("j", bad))
    assert run(c.ttl("j")) == -1.0


def test_expire_with_none_raises_and_changes_nothing():
    # the clarified spec: None is set's default (no expiry); expire must be given a number
    c = Cache(ns()); run(c.set("k", 1))
    with pytest.raises(ValueError):
        run(c.expire("k", None))
    assert run(c.ttl("k")) == -1.0
