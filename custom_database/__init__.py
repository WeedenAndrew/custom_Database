"""custom_Database: a private, Redis-style cache library on one declared Nitric kv store.

    from custom_database import Cache
    cache = Cache("my-namespace")
    await cache.set("price:VIN123", 4200, ttl=3600)

`_cache.py` is the code GAN_ecc's loop built and published, kept byte for
byte (quest/custom-database-structures-20261024-023025, md5 9ff7cee6...).
Change it only through a new spec and a new round, never by hand.
"""
from ._cache import Cache

__all__ = ["Cache"]
