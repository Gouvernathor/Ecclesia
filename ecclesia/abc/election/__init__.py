import abc
from collections import Counter
from collections.abc import Collection

from ..actors import Voter, Party

__all__ = ("Election",)

class Election(abc.ABC):
    """
    Implements the rules to go from a set of opinionated voters to the elected
    representatives.
    """

    @abc.abstractmethod
    def elect(self, pool: Collection[Voter], /) -> Counter[Party]:
        """
        Takes a `pool` of voters such as the Voting classes take, and returns a
        multi-set (a Counter) of elected representatives such as the Attribution
        classes return.
        """
