import abc
from collections import namedtuple, Counter
from . import results_format, voting, attribution
from .. import _settings

class ElectionMethod(namedtuple("ElectionMethod", ("voting_method", "attribution_method")), abc.ABC):
    """Type regrouping a voting method and an attribution method."""

    __slots__ = ()

    __lt__ = __gt__ = __le__ = __ge__ = lambda self, other: NotImplemented

    def election(self, *args, **kwargs):
        return self.attribution_method.attrib(self.voting_method.vote(*args, **kwargs))



class Sortition:
    """Implements a selection by lottery, directly among the population.

    Poses problems that SingleVote+Randomize doesn't, as it does not return
    parties but voters instead.
    """

    __slots__ = ("nseats", "randomobj")

    def __init__(self, nseats, *, randomkey=None, randomobj=None):
        self.nseats = nseats
        if randomobj is None:
            randomobj = _settings.Random(randomkey)
        elif randomkey is not None:
            raise TypeError("Only one of randomobj and randomkey must be provided.")
        self.randomobj = randomobj

    def election(self, pool):
        return Counter(self.randomobj.sample(pool, self.nseats))

ElectionMethod.register(Sortition)
