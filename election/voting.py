import abc
from math import nextafter, floor
from typing import ClassVar, Collection
from . import results_format
from .. import actors, _settings

voting_methods = []

class VotingMethod(abc.ABC):
    """
    Determines the process through which the voters cast their votes.
    Non-instanciable base class.

    By default, classes defining a non-None `name` class attribute will be
    considered valid, usable voting methods.
    Passing a boolean `final` keyword parameter to the class signature will
    override that behavior.

    The default constructor takes a `partis` argument containing the parties
    for which a vote can be cast, and a `randomobj` parameter taking a
    random.Random-like object to use for randomization, defaulting to the
    module's random.
    """

    __slots__ = ()
    return_format: ClassVar = None
    name: ClassVar = None

    def __init__(self, *, partis, randomobj=None):
        if None in (self.name, self.return_format):
            raise TypeError(f"Class {type(self)} is not instantiable.")
        self.partis = partis
        if randomobj is None:
            randomobj = _settings.electrobj
        self.randomobj = randomobj

    def __init_subclass__(cls, final=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if (final is None) and (cls.name is not None) or final:
            voting_methods.append(cls)

    @abc.abstractmethod
    def vote(self, pool:Collection[actors.HasOpinions], /):
        """Returns the ballots cast by the `pool` of voters.

        Override in subclasses.

        `pool` contains the opinionated voters. Generally, though not
        necessarily, Citizens (it can also be Parties). Their disagreement with
        the parties are quantified by the `^` operator, returning values in the
        0-1 range, the higher the stronger disagreement.

        Must return an instance of self.return_format.
        """



class SingleVote(VotingMethod):
    """The most basic and widespread voting method.

    Each voter casts one vote for one of the available candidates, or for none
    of them.
    """

    __slots__ = ()
    return_format = results_format.SIMPLE
    name = "Single Vote"

    def vote(self, pool):
        """
        Tactical voting isn't simulated. Everyone votes for their favorite party.
        """
        partees = list(self.partis)
        scores = results_format.SIMPLE.fromkeys(partees, 0)
        self.randomobj.shuffle(partees)
        for voter in pool:
            # find the party with which disagreement is minimal
            # add it a ballot
            scores[min(partees, key=lambda p: voter ^ p)] += 1
        return scores

class OrderingVote(VotingMethod):
    """Each voter orders all or a subset of the available candidates."""

    __slots__ = ("order_all",) # unused
    return_format = results_format.ORDER
    name = "Positional/Rank Vote"

    def vote(self, pool):
        bigliz = []
        partees = list(self.partis)
        self.randomobj.shuffle(partees)
        for voter in pool:
            ordered = sorted(partees, key=lambda p: voter ^ p)
            bigliz.append(tuple(ordered))
        return results_format.ORDER(bigliz)

class CardinalVote(VotingMethod):
    """Each voter gives a note (or grade) for each of the candidates.

    This one is not as straightforward as the two preceding ones, even setting
    aside strategic voting.
    What do you consider to be the range of grades to cover? From nazis to
    angels, or from the worst present candidate to the best?
    The answer lies only in the minds of the voters.
    The latter is more akin to OrderingVote, so I made the former the default,
    but it causes issues for lower grades so ApprovalVote uses the latter.
    """

    __slots__ = ("grades",) # the number of different grades, >1
    return_format = results_format.SCORES
    name = "Score Vote"

    def __init__(self, grades, **kwargs):
        super().__init__(**kwargs)
        self.grades = grades

    def vote(self, pool):
        """
        Each voter gives a grade to each party proportional to the raw
        disagreement.
        This may yield situations where every party is graded 0, especially with
        lower numbers of grades.
        """
        grades = self.grades
        rv = results_format.SCORES.fromgrades(grades)
        partees = list(self.partis)
        self.randomobj.shuffle(partees)

        # uncorrected version, may return cases where every party is graded 0
        grades = nextafter(grades, .0)
        # if the disagreement is .0, the grade will be grades-1 and not grades
        for voter in pool:
            for parti in partees:
                grad = floor((1-(voter ^ parti)) * grades)
                rv[parti][grad] += 1

        return rv

class BalancedCardinalVote(CardinalVote, final=False):
    """Alternative implementation of CardinalVote."""

    def vote(self, pool):
        """
        Each voter gives a grade to each party, affine wrt its minimum and
        maximum disagreement with the candidate parties only.
        Each voter will give the best grade at least once, and either
        grade all parties equally, or give the worst grade at least once.
        """
        grades = self.grades
        rv = results_format.SCORES.fromgrades(grades)
        partees = list(self.partis)
        self.randomobj.shuffle(partees)

        # balanced version
        grades = nextafter(grades, .0)
        # if the disagreement is .0, the grade will be grades-1 and not grades
        for voter in pool:
            prefs = {parti: 1-(voter ^ parti) for parti in partees}
            minpref = min(prefs.values())
            maxpref = max(prefs.values())

            if minpref != maxpref: # avoid division by zero
                maxpref -= minpref

            for parti in partees:
                grad = floor(grades * (prefs[parti] - minpref) / maxpref)
                rv[parti][grad] += 1

        return rv

class ApprovalVote(BalancedCardinalVote):
    """Each voter approves, or not, each of the candidates.

    Technically a special case of grading vote where grades are 0 and 1,
    but it makes it open to additional attribution methods (proportional ones
    for instance). That's why the format it returns is not the same as
    with CardinalVote.
    If you want a scores-like attribution, use BalancedCardinalVote(2) instead.
    """

    __slots__ = ()
    return_format = results_format.SIMPLE
    name = "Approval Vote"

    def __init__(self, **kwargs):
        super().__init__(grades=2, **kwargs)

    def vote(self, pool):
        scores = super().vote(pool)
        rv = results_format.SIMPLE()
        for parti, (_nays, yeas) in scores.items():
            rv[parti] += yeas
        return rv
