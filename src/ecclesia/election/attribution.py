from collections import defaultdict, Counter
import abc
from fractions import Fraction
from math import sqrt, inf as INF
from statistics import fmean, median
from typing import ClassVar
from . import results_format
from .. import _settings

# TODO: implement consistently
class AttributionFailure(Exception):
    """Raised when an attribution method fails to attribute seats.

    Only when it is a normal limitation of the attribution method, for instance
    when an absolute majority is required but not reached.
    Attribution methods will raise other exceptions.
    """

attribution_methods = []

class Attribution(abc.ABC):
    """
    Determines how the cast votes determine the election.
    Non-instanciable base class.

    By default, classes defining a non-None `name` class attribute will be
    considered valid, usable attribution methods.
    Passing a boolean `final` keyword parameter to the class signature will
    override that behavior.

    All provided subclasses follow the following rule :
    subclasses supporting a contingency attribution method define a
    `contingency` slot, and give it a value in the constructor (passed by
    parameter or not), both replacing the None value set by this class.
    That way :
    getattr(attribution, "contingency", b) -> b if it can takes one, None if not
    hasattr(attribution, "contingency") -> if False, it needs to be given one
    hasattr(attribution, "contingency") and attribution.contingency is not None
        -> it has one, as it should
    The contingency value of an instance should be an attribution method taking
    the same tally format as the instance.

    The default constructor can take either a `randomkey` keyword argument
    (defaulting to None), or `randomobj`, but not both.
    `randomkey` is used for generating a random.Random-like object, used for
    randomization. If `randomobj` is given, it is used instead, allowing for
    several attribution methods' random objects to have the same state.
    """

    __slots__ = ("nseats", "randomobj")
    contingency = None # class attribute overridden as a slot in some subclasses
    taken_format: ClassVar[results_format.formats] = None
    name: ClassVar = None

    def __init__(self, nseats, *, randomkey=None, randomobj=None):
        if self.name is None:
            raise TypeError(f"Class {type(self)} is not instantiable. If it should be, it lacks a name.")

        self.nseats = nseats

        if randomobj is None:
            randomobj = _settings.Random(randomkey)
        elif randomkey is not None:
            raise TypeError("Only one of randomobj and randomkey must be provided.")
        self.randomobj = randomobj

        super().__init__()

    def __init_subclass__(cls, final=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if (final is None) and (cls.name is not None) or final:
            attribution_methods.append(cls)

    @abc.abstractmethod
    def attrib(self, votes, /):
        """Returns the seats attributed from the cast `votes`.

        Override in subclasses.
        `votes` is an instance of self.taken_format.
        Must return a dict(parties:nseats), preferably a Counter,
        where d.total() == nseats.
        Should raise an AttributionFailure when attribution fails due to
        expected conditions, such as a majority threshold not being reached.
        """

class Proportional(Attribution):
    """Abstract base class of proportional attribution methods.

    Natively supports thresholds and contingencies.
    The default constructor (may be overridden by some subclasses) takes both
    as optional keyword arguments.
    When a `threshold` is given (as a percentage of the cast votes), parties
    below it are filtered out of the cast votes tally, which is then passed to
    the `attrib` method. If no party remains, the contingency method is called
    instead.
    Passing `wrap=False` to the subclass's signature will prevent that behavior,
    and allow your `attrib` method to handle thresholds in a different way.
    If no `contingency` is passed and a threshold is provided, a copy of the
    attribution method is used, without the threshold.
    If an attribution method *class* is passed as a `contingency` argument, it
    is instanciated using the same arguments passed to the constructor, except
    for the `threshold` and `contingency` arguments.
    """

    __slots__ = ("threshold", "contingency")
    taken_format = results_format.SIMPLE

    def __init__(self, *args, threshold=None, contingency=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.threshold = threshold
        if (contingency is None) and (threshold is not None):
            contingency = type(self)
        if isinstance(contingency, type):
            contingency = contingency(*args, **kwargs)
        self.contingency = contingency

    def __init_subclass__(cls, wrap=True, **clskwargs):
        super().__init_subclass__(**clskwargs)

        if wrap:
            nothreshold_attrib = cls.attrib

            def attrib(self, votes, /, *args, **kwargs):
                """Wrapper from the Proportional class around a subclass's attrib method."""
                if self.threshold:
                    original_votes = votes
                    thresh = self.threshold * sum(votes.values())
                    votes = self.taken_format({p:v for p,v in votes.items() if v >= thresh})
                    if not votes:
                        return self.contingency.attrib(original_votes, *args, **kwargs)

                return nothreshold_attrib(self, votes, *args, **kwargs)

            cls.attrib = attrib

class RankIndexMethod(Proportional):
    """Abstract base class of rank-index methods - one kind of proportional."""

    __slots__ = ()

    @abc.abstractmethod
    def rank_index_function(self, t, a, /):
        """
        Override in subclasses.

        `t` is the percentage of votes received by a party, as a Fraction.
        `a` is the number of seats already allocated to the party (it will be
        an integer).
        The total number of seats can be accessed as self.nseats.

        The function should be pure (except for constant instance or class
        attributes, such as self.nseats), and return a real value (ideally an
        int or a Fraction for exact calculations).
        The return value should be increasing as `t` rises, and decreasing as
        `a` rises.
        The seat will be attributed to the party maximizing that value.
        """

    def attrib(self, votes, /):
        """
        This implementation is optimized so as to call rank_index_function
        as few times as possible.
        """
        allvotes = sum(votes.values())
        fractions = {p: Fraction(votes[p], allvotes) for p in votes}

        rank_index_values = {p: self.rank_index_function(fractions[p], 0) for p in votes}

        parties = list(votes)
        self.randomobj.shuffle(parties)
        parties.sort(key=rank_index_values.get)

        seats = Counter()

        for _s in range(self.nseats):
            # possibly reimplement this using sortedcollections.ValueSortedDict
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

class DivisorMethod(RankIndexMethod):
    """Abstract base class of divisor methods - one kind of rank-index method."""

    __slots__ = ()

    @classmethod
    def rank_index_function(cls, t, a, /):
        return Fraction(t, cls.divisor(a))

    @staticmethod
    @abc.abstractmethod
    def divisor(k):
        """Explain it yourself if you're so clever !"""



# Majority methods

class _Majority(Attribution):
    """Superclass of SuperMajority and Plurality."""

    __slots__ = ()
    taken_format = results_format.SIMPLE

    def attrib(self, votes, /):
        win = max(votes, key=votes.get)
        if (votes[win] / sum(votes.values())) > self.threshold:
            return Counter({win: self.nseats})
        return self.contingency.attrib(votes)

class Plurality(_Majority):
    """Attribution method where the party with the most votes wins.

    The winner takes all the seats. No threshold.
    """

    __slots__ = ()
    name = "Plurality"
    threshold = 0

class SuperMajority(_Majority):
    """Attribution method where you need a certain percentage of the votes to win all the seats.

    The winner takes all the seats.
    Takes a threshold as a required keyword argument, and a contingency as an
    optional keyword argument.
    If no contingency is provided, raises an AttributionFailure.
    """

    __slots__ = ("threshold", "contingency")
    name = "(Super) Majority"

    def __init__(self, *args, threshold, contingency=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.threshold = threshold
        if contingency is not None:
            self.contingency = contingency


# Ordering-based methods

class InstantRunoff(Attribution):
    """
    Attribution method where the party with the least votes is eliminated, and
    its votes are redistributed to the other parties according to the voters'
    preferences. Repeats until a party reaches an absolute majority of the
    remaining votes, winning all the seats.

    Ballots not ranking all candidates are supported.
    """

    __slots__ = ()
    taken_format = results_format.ORDER
    name = "Instant-Runoff Voting"

    def attrib(self, votes, /):
        blacklisted = set()

        for _i in range(len({party for ballot in votes for party in ballot})):
            first_places = Counter()
            for ballot in votes:
                for party in ballot:
                    if party not in blacklisted:
                        first_places[party] += 1
                        break

            total = first_places.total()
            for parti, score in first_places.items():
                if (score / total) > 0.5:
                    return Counter({parti: self.nseats})
            blacklisted.add(min(first_places, key=first_places.get))
        raise Exception("Shouldn't happen")

class Borda(Attribution):
    """
    Attribution method where each party receives points according to the
    position it has on each ballot, and the party with the most points wins all
    the seats.

    Uses the Modified Borda Count, where the least-ranked candidate receives 1
    point, and unranked candidates receive 0 points.
    So, ballots not ranking all candidates are supported.
    """

    __slots__ = ()
    taken_format = results_format.ORDER
    name = "Borda Count"

    def attrib(self, votes, /):
        scores = Counter()
        for ballot in votes:
            for i, parti in enumerate(reversed(ballot), start=1):
                scores[parti] += i
        return Counter({max(scores, key=scores.get): self.nseats})

class Condorcet(Attribution):
    """
    Attribution method where each party is matched against each other party, and
    the party winning each of its matches wins all the seats.
    If no party wins against all the others, the attribution fails.

    Doesn't support equally-ranked candidates, because the taken format doesn't
    allow it.
    This implementation also doesn't support incomplete ballots.

    The constructor takes an optional `contingency` keyword argument, which
    takes either an Attribution subclass which is passed the same arguments
    except `contingency` itself, or an instance of such a subclass.
    If no contingency is provided, it will instead raise a Condorcet.Standoff
    exception, which is a subclass of AttributionFailure.
    """

    __slots__ = ("contingency",)
    taken_format = results_format.ORDER
    name = "Condorcet method"

    class Standoff(AttributionFailure): pass

    def __init__(self, *args, contingency=None, **kwargs):
        super().__init__(*args, **kwargs)
        if contingency is not None:
            if isinstance(contingency, type):
                contingency = contingency(*args, **kwargs)
            self.contingency = contingency

    def attrib(self, votes, /):
        counts = defaultdict(Counter) # counts[parti1][parti2] = number of ballots where parti1 is ranked before parti2
        majority = len(votes) / 2

        for ballot in votes:
            for i, parti1 in enumerate(ballot):
                for parti2 in ballot[i+1:]:
                    counts[parti1][parti2] += 1

        win = set(counts)
        for parti, partycounter in counts.items():
            for value in (+partycounter).values():
                if value < majority:
                    win.discard(parti)
                    break

        if not win:
            if getattr(self, "contingency", None) is None:
                raise Condorcet.Standoff
            return self.contingency.attrib(votes)
        winner, = win
        return Counter({winner: self.nseats})


# Score-based methods

class AverageScore(Attribution):
    """Gives the seats to the party with the highest average score.

    Tallies where some parties were not graded by everyone are supported.
    """

    __slots__ = ()
    taken_format = results_format.SCORES
    name = "Score method (average rating)"

    def attrib(self, votes, /):
        ngrades = getattr(votes, "ngrades", None) or len(next(iter(votes.values())))
        try:
            return Counter({max(votes, key=(lambda parti: fmean(range(ngrades), votes[parti]))): self.nseats})

        except TypeError:
            # before Python 3.11, fmean doesn't take weights
            pass

        counts = defaultdict(list)
        for parti, grades in votes.items():
            for grade, qty in enumerate(grades):
                counts[parti].extend([grade]*qty)

        return Counter({max(counts, key=(lambda parti: fmean(counts[parti]))): self.nseats})

class MedianScore(Attribution):
    """Gives the seats to the party with the highest median score.

    If there is a tie, the contingency method is called on the tied parties.
    The default contingency is to take the maximum average score.
    The `contingency` parameter takes either an Attribution subclass which is
    passed the same arguments except `contingency` itself, or an instance of
    such a subclass.

    Tallies where some parties were not graded by everyone are supported.
    """

    __slots__ = ("contingency",)
    taken_format = results_format.SCORES
    name = "Majority judgment (median rating)"

    def __init__(self, *args, contingency=AverageScore, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(contingency, type):
            contingency = contingency(*args, **kwargs)
        self.contingency = contingency

    def attrib(self, votes, /):
        counts = defaultdict(list)
        for parti, grades in votes.items():
            for grade, qty in enumerate(grades):
                counts[parti].extend([grade]*qty)

        medians = {parti:median(partigrades) for parti, partigrades in counts.items()}

        winscore = max(medians.values())
        winner, *winners = (parti for parti, med in medians.items() if med == winscore)

        if not winners: # no tie
            return Counter({winner: self.nseats})

        winners.append(winner)
        trimmed_results = results_format.SCORES({parti:votes[parti] for parti in winners})
        return self.contingency.attrib(trimmed_results)


# Proportional methods

class DHondt(DivisorMethod):
    __slots__ = ()
    name = "Proportional (highest averages, Jefferson/D'Hondt)"

    @staticmethod
    def divisor(k):
        return k+1

HighestAverages = DHondt

class Webster(DivisorMethod):
    __slots__ = ()
    name = "Proportional (highest averages, Webster/Sainte-Laguë)"

    @staticmethod
    def divisor(k):
        # return k + .5
        return 2*k + 1 # int maths is more accurate

class Hare(Proportional):
    __slots__ = ()
    name = "Proportional (largest remainder)"

    def attrib(self, votes, /):
        seats = Counter()
        remainders = {}
        nseats = self.nseats
        sumvotes = sum(votes.values())

        for parti, score in votes.items():
            i, r = divmod(score * nseats, sumvotes)
            seats[parti] = i
            remainders[parti] = r

        seats.update(sorted(remainders, key=remainders.get, reverse=True)[:nseats - seats.total()])
        return seats

LargestRemainder = Hare

class HuntingtonHill(DivisorMethod, wrap=False):
    """
    This method requires a bit more creativity and tweaks, since the divisor
    won't work without initial seats value, causing division by zero.
    As a result, passing a threshold is mandatory.
    For a situation where the parties in presence are already limited by other
    means (for example when sharing representatives between US states) to be
    less or equal to the number of seats, you can pass a threshold of 0.
    """

    __slots__ = ()
    name = "Proportional (highest averages, Huntington-Hill)"

    def __init__(self, *args, threshold, contingency=None, **kwargs):
        super().__init__(*args, threshold=threshold, contingency=contingency, **kwargs)

    @staticmethod
    def divisor(k):
        # cast to closest Rational to avoid escalating rounding errors
        return Fraction(sqrt(k*(k+1)))

    def rank_index_function(self, t, a, /):
        if not a:
            return INF
        return super().rank_index_function(t, a)

    def attrib(self, votes, /):
        # Proportional's attrib wrapper won't work, since the method to call
        # after filtering the parties is not the one defined in the class but
        # in the superclass
        # Passing, somehow, the attrib itself as the fallback would first
        # pose some consequent implementation issues, and then prevent having
        # an actual contingency method in the case of no party reaching the
        # threshold.

        original_votes = votes
        threshold = self.threshold * sum(votes.values())
        votes = self.taken_format({p:v for p,v in votes.items() if v >= threshold})
        if not votes:
            return self.contingency.attrib(original_votes)
        return super().attrib(votes)


# Random-based attribution method

class Randomize(Attribution):
    """Randomized attribution.

    Everyone votes, then one ballot is selected at random (per seat to fill).
    """

    __slots__ = ()
    taken_format = results_format.SIMPLE
    name = "Random allotment"

    def attrib(self, votes, /):
        return Counter(self.randomobj.choices(tuple(votes), votes.values(), k=self.nseats))
