import abc
from collections import Counter
from collections.abc import Callable
from fractions import Fraction
from typing import ClassVar, Self

from ..actors import Party
from ...election import ballots

__all__ = ("AttributionFailure", "Attribution", "Proportional")

_notpassed = object()

class AttributionFailure(Exception):
    """Raised when an attribution is unable to attribute seats.

    This exception is only in the case where it's an expected limitation of the
    attribution method, the typical example being the Condorcet standoff, or a
    majority threshold, but a tie could be another example (though ties are
    usually not checked).
    Other exceptions may and will be raised by attributions for other reasons.
    """

class Attribution(abc.ABC):
    """Manages how the results from the ballots determine the allocation of seats.

    This is an abstract base class.
    The constructor assumes that a fixed number of seats will be attributed,
    then accessible as the `nseats` attribute, but a (virtual) subclass may do
    without. In any case, it is usually better for clarity reasons that the
    number of seats allocated by a given attribution method is fixed.

    Each allocation class needs to have a ballot format that it expects and
    accepts.
    """

    taken_ballot_format: ClassVar[type[ballots.formats[Party]]]
    nseats: int

    def __init__(self, nseats: int):
        self.nseats = nseats
        super().__init__()

    @abc.abstractmethod
    def attrib(self, votes, /) -> Counter[Party]:
        """Returns the attribution of seats to the parties based upon the `votes`.

        This is an abstract method that needs to be overridden in subclasses.
        The type of `votes` must be the class's `taken_ballot_format`.
        The return value is a Counter mapping each party to the number of seats
        it won. The return value's .total() should be equal to the instance's
        nseats attribute.

        If the attribution method is expected to fail under expected conditions,
        such as a majority threshold not being reached, it should raise an
        AttributionFailure exception.
        """

class Proportional(Attribution):
    """Abstract base class for proportional attributions.

    This class natively supports an optional `threshold` keyword parameter. It
    is a value between 0 and 1 which disqualifies the candidates that didn't
    reach that portion of the total number of votes.
    Unless the wrap=False keyword argument is passed to the class definition,
    that disqualification will be applied automatically, before the attrib
    method is called. In that case, if no party reaches the threshold, the
    contingency attribution will be used with all parties, and if no contingency
    is provided, an AttributionFailure will be raised.
    You should pass wrap=False if you want to manage the threshold and/or
    contingency yourself or in a different way.

    The `contingency` optional keyword parameter provides the fallback in case
    the threshold is not reached by any candidate. It will not be called if the
    attrib method raises an AttributionFailure exception for any other reason -
    though you are free to call it yourself.
    It takes either an Attribution class or an Attribution instance. If an
    Attribution class is passed or used, it is instantiated with the same
    arguments that reach the Attribution constructor, except for the `threshold`
    and `contingency` parameters.
    It defaults to the class of the object, which means that the fallback is the
    same attribution method but without the threshold.
    Passing None will disable the fallback, and force an AttributionFailure to
    be raised if no candidate reach the threshold.
    If wrap=False, the `contingency` parameter only sets the `contingency`
    attribute and does nothing of it.
    """

    taken_ballot_format = ballots.Simple[Party]

    def __init_subclass__(cls, wrap=True, **clskwargs):
        super().__init_subclass__(**clskwargs)

        if wrap:
            nothreshold_attrib = cls.attrib

            def attrib(self: Self, votes: ballots.Simple[Party], /, *args, **kwargs) -> Counter[Party]:
                """Wrapper from the Proportional class around a subclass's attrib method."""
                if self.threshold:
                    original_votes = votes
                    votes_thresh = self.threshold * votes.total()
                    votes = ballots.Simple({p: v for p, v in votes.items() if v >= votes_thresh})
                    if not votes:
                        try:
                            contingency_attrib = self.contingency.attrib # type: ignore
                        except AttributeError:
                            raise AttributionFailure("No party reached the threshold")
                        else:
                            return contingency_attrib(original_votes, *args, **kwargs)

                return nothreshold_attrib(self, votes, *args, **kwargs)

            cls.attrib = attrib

    threshold: float
    contingency: Attribution|None

    def __init__(self, *args,
            threshold: float = .0,
            contingency: Attribution|type[Attribution]|None = _notpassed, # type: ignore
            **kwargs):
        super().__init__(*args, **kwargs)

        self.threshold = threshold

        if (contingency is _notpassed) and threshold:
            contingency = self.__class__
        if isinstance(contingency, type):
            contingency = contingency(*args, **kwargs)
        self.contingency = contingency

    attrib: Callable[[Self, ballots.Simple[Party]], Counter[Party]]

class RankIndexMethod(Proportional):
    """Abstract base class for rank-index methods - one kind of proportional attribution.

    This class implements a mixin attrib method, and has an abstract
    rank_index_function method that should be overridden in subclasses.
    """

    @abc.abstractmethod
    def rank_index_function(self, t: Fraction, a: int, /) -> int|float|Fraction:
        """
        This is an abstract method that should be overridden in subclasses.

        `t` is the percentage of votes received by a party, as a Fraction.
        `a` is the number of seats already attributed to that same party.
        The total number of seats can be accessed as self.nseats.

        The function should be pure : it should not take into account any value
        other than the two parameters and instance or class attributes.
        It should return a real value, ideally an int or a Fraction for exact
        calculations.
        The return value should be increasing as `t` rises, and decreasing as
        `a` rises.
        The higher the return value, the higher chance for the party to receive
        another seat.
        """

    def attrib(self, votes: ballots.Simple[Party], /) -> Counter[Party]:
        """
        This implementation is optimized so as to call rank_index_function as
        few times as possible.
        """
        allvotes = votes.total()
        fractions = {p: Fraction(v, allvotes) for p, v in votes.items()}

        rank_index_values = {p: self.rank_index_function(f, 0) for p, f in fractions.items()}

        parties = sorted(tuple(votes), key=rank_index_values.__getitem__)

        seats = Counter()

        for _s in range(self.nseats):
            # may be reimplemented using sortedcollections.ValueSortedDict
            winner = parties.pop()
            seats[winner] += 1
            rank_index_values[winner] = self.rank_index_function(fractions[winner], seats[winner])
            for i, p in enumerate(parties):
                if rank_index_values[p] >= rank_index_values[winner]:
                    parties.insert(i, winner)
                    break
            else:
                parties.append(winner)

        return seats
