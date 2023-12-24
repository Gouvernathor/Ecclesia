from collections import defaultdict, Counter
import abc
from fractions import Fraction
from statistics import fmean, median
from typing import ClassVar
from . import results_format, _settings

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

            def attrib(self, results, *args, **kwargs):
                """Wrapper from the Propotional class around a subclass's attrib method."""
                if self.threshold:
                    original_results = results
                    thresh = self.threshold * sum(results.values())
                    results = self.taken_format({p:v for p,v in results.items() if v >= thresh})
                    if not results:
                        return self.contingency.attrib(original_results, *args, **kwargs)

                return nothreshold_attrib(self, results, *args, **kwargs)

            cls.attrib = attrib

class RankIndexMethod(Proportional):
    """Abstract base class of rank-index methods - one kind of proportional."""

    __slots__ = ()

    def __key(self, votes, seats):
        allvotes = sum(votes.values())
        def f(p):
            return self.rank_index_function(Fraction(votes[p], allvotes), seats[p])
        return f

    @abc.abstractmethod
    def rank_index_function(self, t, a, /):
        """
        Override in subclasses.

        `t`, is the percentage of votes received by a party, as a Fraction.
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
        seats = Counter()

        for _s in range(self.nseats):
            seats[max(votes, key=self.__key(votes, seats))] += 1

        return seats

class DivisorMethod(RankIndexMethod):
    """Abstract base class of divisor methods - one kind of rank-index method."""

    __slots__ = ()

    def rank_index_function(self, t, a, /):
        return Fraction(t, self.divisor(a))

    @abc.abstractmethod
    def divisor(self, k):
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
    """

    __slots__ = ()
    taken_format = results_format.ORDER
    name = "Borda Count"

    def attrib(self, votes, /):
        scores = Counter()
        for ballot in votes:
            for i, parti in enumerate(reversed(ballot),start=1):
                scores[parti] += i
        return Counter({max(scores, key=scores.get): self.nseats})

class Condorcet(Attribution):
    """
    Attribution method where each party is matched against each other party, and
    the party with the most wins wins all the seats.
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

    def divisor(self, k):
        return k+1

HighestAverages = DHondt

class Webster(DivisorMethod):
    __slots__ = ()
    name = "Proportional (highest averages, Webster/Sainte-Laguë)"

    def divisor(self, k):
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


class Randomize(Attribution):
    """Randomized attribution.

    Everyone votes, then one ballot is selected at random (per seat to fill).
    """

    __slots__ = ()
    taken_format = results_format.SIMPLE
    name = "Random allotment"

    def attrib(self, votes, /):
        return Counter(self.randomobj.choices(tuple(votes), votes.values(), k=self.nseats))
