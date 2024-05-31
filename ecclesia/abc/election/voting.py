import abc
from collections.abc import Collection
from typing import ClassVar

from . import Voter, Party
from ...election.ballots import formats

class Voting(abc.ABC):
    """An abstract base class representing the rules for citizens to cast ballots."""

    ballot_format: ClassVar[type[formats[Party]]]

    @abc.abstractmethod
    def vote(self, pool: Collection[Voter], /) -> formats[Party]:
        """Returns the ballots cast by the `pool` of voters.

        This is an abstract method that needs to be overridden in subclasses.

        `pool` contains the opinionated voters. They are generally citizens, but
        it could also be parties in some situations. Their disagreement with the
        candidate parties are quantified by the `^` operator, supported by the
        HasOpinions class.

        Must return an instance of the class's ballot_format.
        """
