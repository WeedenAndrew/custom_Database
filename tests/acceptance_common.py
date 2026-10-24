import asyncio, uuid

LOOP = asyncio.get_event_loop()


def run(c):
    return LOOP.run_until_complete(c)


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def ns(tag="t"):
    return f"{tag}-{uuid.uuid4().hex[:10]}"
