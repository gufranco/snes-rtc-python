from __future__ import annotations

CRYSTAL_HZ = 32768

LOW_SECONDS = 0.0078

LOCKOUT_SECONDS = 0.000125

FAST_HZ = 64

LOW = 0

OPEN = 1


def whole_ticks(rate: int, seconds: float) -> int:
    return round(rate * seconds)


class Crystal:
    __slots__ = ("adjust_at", "edge", "last", "rate")

    def __init__(self, rate: int = 1) -> None:
        self.rate = rate
        self.last: int | None = None
        self.edge: int | None = None
        self.adjust_at: int | None = None

    @property
    def continuous(self) -> bool:
        return self.rate > 1

    def seconds(self, ticks: int) -> int:
        return ticks // self.rate

    def low_ticks(self) -> int:
        return whole_ticks(self.rate, LOW_SECONDS)

    def lockout_ticks(self) -> int:
        return whole_ticks(self.rate, LOCKOUT_SECONDS)

    def fast_edge(self, now: int) -> int | None:
        period = self.rate // FAST_HZ
        if not period or self.last is None:
            return None
        edge = now // period * period
        return edge if edge > self.last else None

    def second_edge(self, now: int, gap: int, step: int) -> int:
        return (self.seconds(now) - gap + step) * self.rate

    def pulsing(self, now: int) -> bool:
        return self.edge is not None and now < self.edge + self.low_ticks()

    def locked(self, now: int) -> bool:
        return self.adjust_at is not None and now < self.adjust_at

    def settling(self, now: int) -> bool:
        return self.adjust_at is not None and now >= self.adjust_at
