from collections import Counter, defaultdict
from collections.abc import Sequence
from fractions import Fraction
from statistics import fmean, median
from typing import Any

from . import ballots
from ..abc.actors import Party
from ..abc.election.attribution import Attribution, AttributionFailure, DivisorMethod, Proportional

__all__ = (
    "Majority",
    "InstantRunoff", "Borda", "Condorcet",
    "AverageScore", "MedianScore",
    "DHondt", "HighestAverages",
    "Webster", "SainteLague",
    "Hare", "LargestRemainder",
)

_notpassed: Any = object()

# Simple-based, majority

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

# Order-based

class InstantRunoff(Attribution):
    """
    Attribution method where the party with the least votes is eliminated, and
    its votes are redistributed to the other parties according to the voters'
    preferences. It repeats until a party reaches an absolute majority of the
    remaining votes, winning all the seats.
    """
    """
    This only supports ballots in which all the candidates are ranked.
    (Actually, not sure...)
    """
    taken_ballot_format = ballots.Order[Party]

    def attrib(self, votes: ballots.Order[Party], /) -> Counter[Party]:
        blacklist = set()

        parties = {party for ballot in votes for party in ballot}
        for _i in range(len(parties)):
            first_places = Counter()
            for ballot in votes:
                for party in ballot:
                    if party not in blacklist:
                        first_places[party] += 1
                        break

            total = first_places.total()
            for parti, score in first_places.items():
                if score * 2 > total:
                    return Counter({parti: self.nseats})
            blacklist.add(min(first_places, key=first_places.__getitem__))
        raise Exception("This should never be reached")

    def _attrib2(self, votes: ballots.Order[Party], /) -> Counter[Party]:
        blacklist = set()

        ballots_by_top_party: dict[Party, list[Sequence[Party]]] = defaultdict(list)
        for ballot in votes:
            if not ballot:
                continue
            ballots_by_top_party[ballot[0]].append(ballot)

        while ballots_by_top_party:
            total = sum(map(len, ballots_by_top_party.values()))
            for party, ballots in ballots_by_top_party.items():
                if len(ballots) * 2 > total:
                    return Counter({party: self.nseats})

            loser = min(ballots_by_top_party, key=lambda party: len(ballots_by_top_party[party]))
            blacklist.add(loser)
            for ballot in ballots_by_top_party.pop(loser):
                while ballot and (ballot[0] in blacklist):
                    ballot = ballot[1:]
                if ballot:
                    ballots_by_top_party[ballot[0]].append(ballot)
        raise Exception("This should never be reached")

class Borda(Attribution):
    """
    Attribution method where each party receives points according to the rank
    it has on each ballot. The party with the most points wins all the seats.

    Uses the Modified Borda Count, where the least-ranked party receives 1
    point, and unranked candidates receive 0 points.
    So, ballots not ranking all candidates are supported.
    """
    taken_ballot_format = ballots.Order[Party]

    def attrib(self, votes: ballots.Order[Party], /) -> Counter[Party]:
        scores = Counter()
        for ballot in votes:
            for i, party in enumerate(reversed(ballot), start=1):
                scores[party] += i
        return Counter({max(scores, key=scores.__getitem__): self.nseats})

class Condorcet(Attribution):
    """
    Attribution where the party that wins in a head-to-head matchup against
    every other party wins all the seats.
    If no such party exists, the attribution fails.

    This doesn't support equally-ranked candidates - though the ballot format
    doesn't support it in the first place.
    This implementation also doesn't support incomplete ballots.
    """
    taken_ballot_format = ballots.Order[Party]

    # TODO: add contingency support

    class Standoff(AttributionFailure): pass

    def attrib(self, votes: ballots.Order[Party], /) -> Counter[Party]:
        # number of ballots where party1 wins against party2
        counts: dict[Party, Counter[Party]] = defaultdict(Counter)
        majority = len(votes) / 2

        for ballot in votes:
            for i, party1 in enumerate(ballot, start=1):
                for party2 in ballot[i:]:
                    counts[party1][party2] += 1

        possible_win = set(counts)
        for party, partycounter in counts.items():
            for value in (+partycounter).values():
                if value < majority:
                    possible_win.discard(party)
                    break

        if possible_win:
            winner, = possible_win
            return Counter({winner: self.nseats})
        raise Condorcet.Standoff

# Score-based

class AverageScore(Attribution):
    """Gives the seats to the party with the highest average score.

    Tallies where some parties are not graded by every ballot are supported.
    """
    taken_ballot_format = ballots.Scores[Party]

    def attrib(self, votes: ballots.Scores[Party], /) -> Counter[Party]:
        ngrades = votes.ngrades
        winner = max(votes, key=(lambda party: fmean(range(ngrades), votes[party])))
        return Counter({winner: self.nseats})

class MedianScore(Attribution):
    """Gives the seats to the party with the highest median score.

    This is also called "majority judgment".

    If there is a tie, the contingency method is called on the tied parties.
    The default contingency is to take the maximum average score.

    Tallies where some parties are not graded by every ballot are supported.
    """
    taken_ballot_format = ballots.Scores[Party]

    # TODO: maybe implement contingency in a canonical way
    # TODO: maybe allow the contingency to receive the vanilla vote and not the trimmed vote

    def __init__(self, *args, contingency: Attribution = _notpassed, **kwargs):
        super().__init__(*args, **kwargs)
        if contingency is _notpassed:
            contingency = AverageScore(*args, **kwargs)
        self.contingency = contingency

    def attrib(self, votes: ballots.Scores[Party], /) -> Counter[Party]:
        allgrades_per_party: dict[Party, list[int]] = defaultdict(list)
        for party, grades in votes.items():
            for grade, qty in enumerate(grades):
                allgrades_per_party[party].extend([grade] * qty)

        medians = {party: median(partygrades) for party, partygrades in allgrades_per_party.items()}

        winscore = max(medians.values())
        winner, *other_winners = (party for party, score in medians.items() if score == winscore)

        if not other_winners: # no tie
            return Counter({winner: self.nseats})

        winners = [winner, *other_winners]
        trimmed_votes = ballots.Scores({party: votes[party] for party in winners})
        return self.contingency.attrib(trimmed_votes)

# Simple-based, proportionals

class DHondt(DivisorMethod):
    @staticmethod
    def divisor(k, /):
        return k+1

HighestAverages = DHondt

class Webster(DivisorMethod):
    @staticmethod
    def divisor(k, /):
        # return k + .5 # inaccurate
        # return Fraction(1, 2) + k # accurate but slow
        return 2*k + 1

SainteLague = Webster

class Hare(Proportional):
    def attrib(self, votes: ballots.Simple[Party], /) -> Counter[Party]:
        seats = Counter()
        remainders = {}
        nseats = self.nseats
        sumvotes = votes.total()

        for parti, score in votes.items():
            seats[parti], remainders[parti] = divmod(score * nseats, sumvotes)

        seats.update(sorted(remainders, key=remainders.__getitem__, reverse=True)[:nseats - seats.total()])
        return seats

LargestRemainder = Hare
