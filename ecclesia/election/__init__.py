from collections import Counter
from collections.abc import Collection
import random

from ..abc.actors import HasOpinions, Party, Voter
from ..abc.election import Election
from ..abc.election.voting import Voting
from ..abc.election.attribution import Attribution

__all__ = ("ConcreteBaseElection", "Sortition")

class ConcreteBaseElection(Election):
    """
    This is a base class, but not quite an abstract one since it can be used
    as-is.
    """
    voting: Voting
    attribution: Attribution

    def __init__(self, voting: Voting, attribution: Attribution, /):
        self.voting = voting
        self.attribution = attribution

    def elect(self, pool: Collection[Voter]) -> Counter[Party]:
        return self.attribution.attrib(self.voting.vote(pool))

class Sortition(Election):
    """Implements a selection by lottery, directly among a population.

    This poses problems that ConcreteBaseElection(SingleVote, Randomize)
    doesn't, as it does not elect parties but citizens instead.
    """

    def __init__(self, nseats: int, *,
            randomseed=None,
            randomobj: random.Random|None = None,
            ):
        """
        The optional `randomobj` parameter can be used to provide a random
        object (following the random.Random class specification) to
        deterministically shuffle the parties so that the ties and the order
        in which they are then passed to the attribution method are evenly
        chanced. You can also pass a `randomseed` to deterministically seed a
        new random object.
        """
        self.nseats = nseats
        if randomobj is None:
            randomobj = random.Random(randomseed)
        self.randomobj = randomobj

    def elect(self, pool: Collection[HasOpinions]) -> Counter[HasOpinions]:
        return Counter(self.randomobj.sample(tuple(pool), self.nseats))
