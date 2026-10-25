import asyncio, uuid

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)   # set BEFORE the Nitric SDK is imported: its own get_event_loop() at import
                               # then finds this loop (Python 3.14 makes get_event_loop() with no loop an error)


def run(c):
    return LOOP.run_until_complete(c)


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def ns(tag="t"):
    return f"{tag}-{uuid.uuid4().hex[:10]}"
