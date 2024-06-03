from collections import Counter
from collections.abc import Collection
from fractions import Fraction
from typing import Any

from . import ballots
from ..abc.actors import Party
from ..abc.election.attribution import Attribution, AttributionFailure

__all__ = ("Majority",)

_notpassed: Any = object()

class Majority(Attribution):
    """
    This implements a family of attribution methods, including the
    single-turn first-past-the-post plurality, the single-turn single-winner
    absolute majority (or qualified super-majority), the majority list ballot,
    but also the multi-winner majority ballot.

    The contingency works differently as with proportionals, in that it applies
    after the main part of the attribution process rather than before it.

    The ways to classify them are as follows. (Note that in each case the voting
    may be simple or by approval.)
    - If there is a single seat to be attributed (nseats=1), then multi_winner
      is irrelevant.
      - If there is no threshold, then it is a single-turn first-past-the-post
        plurality attribution, meaning that the winner is the candidate with the
        most votes, period. This is the system used for british house elections.
      - If there is a threshold, then it fits the first turn of a two-turn
        majority attribution, such as the french presidential and legislative
        elections.
    - Multiple seats can be attributed in two ways : with multiple winning
      parties, or with a single winning party.
      - If there is a single winning party, then it is a majority list ballot :
        lists compete, and the list with the most ballots wins all the seats.
        That's how 50% of the seats are allotted in french municipal elections.
      - If there are multiple winning parties, then the name (and strategies)
        for that ballot vary a lot depending on the number of votes that each
        voter can cast : single non-transferable vote, limited voting, plurality
        block voting, block approval voting, etc.
        In any case, this framework is not adapted to this situation, for two
        main reasons :
        - Each party typically presents as many candidates as there are seats
          to fill, but this framework typically doesn't differenciate between
          the candidates and the set of existing parties.
        - The results are usually deeply influenced by tactical voting, which
          the concrete classes implemented in this framework don't simulate.
    """
    taken_ballot_format = ballots.Simple[Party]
    threshold: float|Fraction
    contingency: Attribution|None
    multi_winner: bool

    def __init__(self, *args,
            threshold: float|Fraction = 0,
            contingency: Attribution|None = _notpassed,
            multi_winner: bool = False,
            **kwargs):
        super().__init__(*args, **kwargs)
        self.threshold = threshold

        # TODO: implement the contingency manager
        if (contingency is _notpassed) and threshold:
            contingency = self.__class__(*args, multi_winner=multi_winner, **kwargs)
        self.contingency = contingency

        self.multi_winner = multi_winner

    def attrib(self, votes: ballots.Simple[Party], /) -> Counter[Party]:
        if self.multi_winner:
            nseats = self.nseats
            if len(votes) < nseats:
                # this is not an attributionerror, as no matter the will of the
                # voters, such a situation has no solution
                raise ValueError("Not enough parties to fill all seats")

            winners = sorted(votes, key=votes.__getitem__, reverse=True)[:nseats]
            if votes[winners[-1]] > (self.threshold * votes.total()):
                return Counter({p: 1 for p in winners})
            msg = "Not enough parties reached the threshold"

        else:
            winner = max(votes, key=votes.__getitem__)
            if votes[winner] > (self.threshold * votes.total()):
                return Counter({winner: self.nseats})
            msg = "No party reached the threshold"

        try:
            contingency_attrib = self.contingency.attrib # type: ignore
        except AttributeError:
            raise AttributionFailure(msg)
        else:
            return contingency_attrib(votes)
