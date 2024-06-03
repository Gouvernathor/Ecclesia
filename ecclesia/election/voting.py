
from collections.abc import Collection
from math import nextafter, trunc
import random
from typing import ClassVar

from . import ballots
from ..abc.actors import Voter, Party
from ..abc.election.voting import Voting

__all__ = ("SingleVote", "OrderingVote", "CardinalVote", "ApprovalVote")

class _VotingBase(Voting):
    name: ClassVar[str]

    def __init__(self, *,
            parties: Collection[Party],
            randomobj: random.Random|None = None,
            randomseed=None,
            ):
        """
        The constructor of this class takes a `parties` keyword-only parameter
        containing the parties for which a vote can be cast in this election.
        The optional `randomobj` parameter can be used to provide a random
        object (following the random.Random class specification) to
        deterministically shuffle the parties so that the ties and the order
        in which they are then passed to the attribution method are evenly
        chanced. You can also pass a `randomseed` to deterministically seed a
        new random object.
        """
        self.parties = parties
        if randomobj is None:
            randomobj = random.Random(randomseed)
        self.randomobj = randomobj

class SingleVote(_VotingBase):
    """The most basic and widespread voting method.

    Each voter casts one vote for one of the available candidates, or for none
    of them.
    This is guaranteed to include all the parties in the returned value, even
    with a count of 0 ballots.
    """

    ballot_format = ballots.Simple
    name = "Single Vote"

    def vote(self, pool: Collection[Voter], /) -> ballots.Simple[Party]:
        """
        Tactical voting isn't simulated. Everyone votes for their favorite party.
        """
        parties = list(self.parties)
        scores = ballots.Simple.fromkeys(parties, 0)
        self.randomobj.shuffle(parties)
        for voter in pool:
            # find the party with which disagreement is minimal
            # add it a ballot
            scores[min(parties, key=lambda party: voter ^ party)] += 1
        return scores

class OrderingVote(_VotingBase):
    """Each voter orders the available candidates."""

    ballot_format = ballots.Order
    name = "Positional/Rank Vote"

    def vote(self, pool: Collection[Voter], /) -> ballots.Order[Party]:
        bigliz = []
        parties = list(self.parties)
        self.randomobj.shuffle(parties)
        for voter in pool:
            bigliz.append(tuple(sorted(parties, key=lambda party: voter ^ party)))
        return ballots.Order(bigliz)

class CardinalVote(_VotingBase):
    """Each voter gives a grade or score for each of the candidates.

    Theoretically a superset of ApprovalVote.
    """
    """
    This one is not as straightforward to simulate as the previous ones, even
    setting aside strategic voting.
    What will each voter consider to be the range of grades to cover? From nazis
    to angels, or from the worst to the best of the candidates that are in front
    of us?
    The latter is more akin to OrderingVote, so I used the former, but it causes
    issues when the number of grades is low.
    This is guaranteed to include all the parties in the returned value.
    """

    ballot_format = ballots.Scores
    name = "Score Vote"
    ngrades: int

    def __init__(self, ngrades: int, **kwargs):
        super().__init__(**kwargs)
        self.ngrades = ngrades

    def vote(self, pool: Collection[Voter], /) -> ballots.Scores[Party]:
        """
        Each voter gives a grade to each party proportionally to the raw
        disagreement.
        This may yield situations where every party is graded 0, especially when
        the number of grades is low.
        """
        ngrades = self.ngrades
        scores = ballots.Scores.fromgrades(ngrades)
        parties = list(self.parties)
        self.randomobj.shuffle(parties)

        # if the disagreement is 0, the grade will be grades-1 and not grades
        naftergrades = nextafter(ngrades, .0)

        for voter in pool:
            for party in parties:
                grade = trunc((1-(voter ^ party)) * naftergrades)
                scores[party][grade] += 1
        return scores

class BalancedCardinalVote(CardinalVote):
    """Alternate implementaton of CardinalVote."""

    def vote(self, pool: Collection[Voter], /) -> ballots.Scores[Party]:
        """
        The grade that each voter will give to each party is affine with
        regard to the voter's minimum and maximum disagreement with the
        candidate parties only.
        As a result, each voter will give the best grade at least once, and
        either give the worst grade at least once or give the best grade to all
        parties.
        """
        ngrades = self.ngrades
        scores = ballots.Scores.fromgrades(ngrades)
        parties = list(self.parties)
        self.randomobj.shuffle(parties)

        # if the disagreement is 0, the grade will be grades-1 and not grades
        naftergrades = nextafter(ngrades, .0)

        for voter in pool:
            prefs = {party: 1-(voter ^ party) for party in parties}
            minpref = min(prefs.values())
            maxpref = max(prefs.values())

            if minpref != maxpref: # avoid division by zero
                maxpref -= minpref

            for party in parties:
                grade = trunc(naftergrades * (prefs[party] - minpref) / maxpref)
                scores[party][grade] += 1

        return scores

class ApprovalVote(BalancedCardinalVote):
    """Each voter approves or disapproves of each of the candidates.

    Technically a special case of grading vote where grades are 0 and 1, but it
    opens to a different set of additional attribution methods (proportionals
    for instance). That's why the format it returns is not the same as with
    CardinalVote.
    If you want a scores-like attribution, use CardinalVote(2) instead.
    This is guaranteed to include all the parties in the returned value, even
    with a count of 0 ballots.
    """

    ballot_format = ballots.Simple
    name = "Approval Vote"

    def __init__(self, **kwargs):
        super().__init__(ngrades=2, **kwargs)

    def vote(self, pool: Collection[Voter], /) -> ballots.Simple[Party]:
        scores = super().vote(pool)
        return ballots.Simple({party: yeas for party, (_nays, yeas) in scores.items()})
