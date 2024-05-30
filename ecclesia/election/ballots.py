"""Module storing the various formats handled by election methods.

The formats are Simple, Order and Scores.
Each represents what you get after opening each ballot, under different
voting systems.

The `formats` pseudo-type can be used for type checks/annotations.
"""

from collections import Counter
from collections.abc import Iterable, MutableSequence, Sequence

__all__ = ("Simple", "Order", "Scores", "formats")

class Simple[P](Counter[P]):
    """Simple : Counter(party : number of ballots)

    {PS : 5, LR : 7} -> 5 ballots for PS, 7 for LR
    """

    __slots__ = () # useless for Counter

    @classmethod
    def fromkeys(cls, keys: Iterable[P], value: int, /) -> "Simple[P]":
        return cls(dict.fromkeys(keys, value))

class Order[P](tuple[Sequence[P], ...]):
    """Order : iterable(iterable(parties ordered by decreasing preference))

    [(LR, PS, LFI), (LFI, PS,), ] -> one voter prefers LR then PS then LFI,
                                     another prefers LFI then PS and didn't rank LR

    max(len(tup) for tup in result) <= (number of candidates) - 1
                                    == if votingmethod.order_all

    There can be no tie between candidates within a ballot.
    Note that not ranking all the candidates is permitted by this type, but some
    attribution methods may not support it.
    """

    __slots__ = ()

class Scores[P](dict[P, MutableSequence[int]]):
    """Scores : dict(party : iterable(number of ballots for each grade))

    {PS : (0, 2, 5, 9, 1)} -> PS received the worst grade 0 times, the best grade 1 time and you get it.
    (len(tup) for tup in result.values()) is constant, equal to votingmethod.grades
    if the voter must grade all the candidates, (sum(tup) for tup in result.values()) is constant and equal to the number of voters

    If the `ngrades` attribute was set, any party not present in the dict will
    return an all-0 list of grades.
    It is advised to either pass arguments to the default constructor (which is
    the same as dict's), or to pass the number of grades to the alternative
    constructor `fromgrades` which will build an empty instance.
    Otherwise, the `ngrades` attribute will not be set and checking for
    unlisted parties will raise an exception.
    """

    __slots__ = ("ngrades")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self:
            self.ngrades = len(next(iter(self.values())))

    @classmethod
    def fromgrades(cls, ngrades: int, /) -> "Scores[P]":
        self = cls()
        self.ngrades = ngrades
        return self

    def __missing__(self, key: P, /) -> MutableSequence[int]:
        rv = [0]*self.ngrades
        # self[key] = rv
        return rv

type formats[P] = Simple[P]|Order[P]|Scores[P]
