init python in results_format:
    # SIMPLE : dict(parti : nombre de voix)
    #       {PS : 5, LR : 7} -> 5 voix pour le PS, 7 pour LR
    # ORDER : iterable(iterable(partis ordonnés par préférence décroissante))
    #       [(LR, PS, LFI), (LFI, PS,), ] -> un électeur préfère LR puis PS puis LFI,
    #                                        un autre préfère LFI puis le PS et n'a pas classé LR
    #       max(len(tup) for tup in result) <= (nombre de candidats) - 1
    #                                       == si votingmethod.order_all
    #       Ne pas classer tous les candidats est permis, mais pas d'ex-aequo
    # SCORES : dict(parti : iterable(nombre de voix pour chaque note))
    #       {PS : (0, 2, 5, 9, 1)} -> le PS a reçu 0 fois la pire note, 1 fois la meilleure et t'as compris
    #       (len(tup) for tup in result.values()) est constant, égal à votingmethod.grades

    class SIMPLE(dict):
        __slots__ = ()
    class ORDER(tuple):
        __slots__ = ()
    class SCORES(dict):
        __slots__ = ()

    formats = (SIMPLE, ORDER, SCORES)

init python:
    import abc, inspect

    voting_methods = []

    class VotingMethod(abc.ABC):
        """
        Determines the process through which the voters cast their votes.
        Non-instanciable class.
        """
        __slots__ = ()
        return_format = None # class attribute, not instance attribute

        name = None # class attribute, not instance attribute
        # wrap in _() to make it translatable

        def __init__(self):
            if None in (self.name, self.return_format):
                raise TypeError(f"Class {type(self)} is not instantiable.")

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            if cls.name is not None:
                voting_methods.append(cls)

        @abc.abstractmethod
        def vote(self, pool):
            """
            Returns an instance of self.return_format.
            """

    class SingleVote(VotingMethod):
        """
        Each voter casts one vote for one of the available candidates, or for none of them.
        """
        __slots__ = ()
        return_format = results_format.SIMPLE
        name = _("Single Vote")

        def vote(self, pool):
            """
            Tactical voting isn't simulated. Everyone votes for their favorite party.
            """
            scores = self.return_format.fromkeys(partis, 0)
            partees = list(partis)
            electrobj.shuffle(partees)
            for citizen in pool:
                # sélectionner le parti avec lequel le désaccord est le plus petit
                # lui ajouter une voix
                scores[min(partees, key=(lambda p:p.disagree(citizen)))] += 1
            return scores

    class OrderingVote(VotingMethod):
        """
        Each voter orders all (or a subset) of the available candidates.
        """
        __slots__ = ("order_all")
        return_format = results_format.ORDER
        name = _("Positional/Rank Vote")

        def vote(self, pool):
            bigliz = self.return_format()
            partees = list(partis)
            electrobj.shuffle(partees)
            for citizen in pool:
                ordered = sorted(partees, key=(lambda p:p.disagree(citizen)))
                bigliz.append(tuple(ordered))
            return bigliz

    class CardinalVote(VotingMethod):
        """
        Each voter gives a note (or grade) for each of the candidates.
        """
        __slots__ = ("grades") # le nombre de notes différentes, >1
        return_format = results_format.SCORES
        name = _("Score Vote")

    class ApprovalVote(CardinalVote):
        """
        Each voter approves, or not, each of the candidates.

        Technically a special case of grading vote where grades are 0 and 1,
        but it makes it open to additional attribution methods (proportional ones for instance).
        The format it returns data in, however, is (potentially) not the same as CardinalVote.
        """
        __slots__ = ()
        return_format = results_format.SIMPLE
        name = _("Approval Vote")

        def __init__(self, *args):
            self.grades = 2

init python:
    from collections import defaultdict
    from statistics import fmean

    attribution_methods = []

    def listed_attrib(func):
        attribution_methods.append(func)
        return func

    class Attribution(abc.ABC):
        """
        Determines how the votes determine the election.
        Non-instanciable class.
        """
        __slots__ = ("nseats", "randomobj")
        contingency = None
        # getattr(attribution, "contingency", b) -> b if it can take one, None if not
        # hasattr(attribution, "contingency") -> if False, it needs to be given one
        # hasattr(attribution, "contingency") and attribution.contingency is not None -> it has one as it should
        # the contingency is given a default (or not) by classes using it in the constructor
        # or set afterward by setattr

        taken_format = None # class attribute, not instance attribute
        # `accepts` or `can_follow` staticmethod/classmethod, to say if it accepts a given voting method or not ?

        name = None # class attribute, not instance attribute
        # wrap in _() to make it translatable

        def __init__(self, nseats, randomobj=None, randomkey=None):
            if self.name is None:
                raise TypeError(f"{type(self)} is not instanciable. If it should be, it lacks a name.")
            self.nseats = nseats
            if None not in (randomobj, randomkey):
                raise TypeError("Only one of randomobj and randomkey must be provided.")
            if randomobj is None:
                randomobj = renpy.random.Random(randomkey)
            self.randomobj = randomobj
            super().__init__()

        @abc.abstractmethod
        def attrib(self, results): pass

    class Majority(Attribution):
        """
        Superset of SuperMajority and Plurality.
        """
        __slots__ = ()
        taken_format = results_format.SIMPLE

        def attrib(self, results):
            win = max(results, key=results.get)
            if (results[win] / sum(results.values())) > self.threshold:
                return [(win, self.nseats)]
            return self.contingency(results)

    @listed_attrib
    class Plurality(Majority):
        __slots__ = ()
        threshold = 0
        name = _("Plurality")

    @listed_attrib
    class SuperMajority(Majority):
        __slots__ = ("threshold", "contingency")
        name = _("(Super) Majority")

        def __init__(self, *args, threshold, **kwargs):
            self.threshold = threshold

    @listed_attrib
    class InstantRunoff(Attribution):
        __slots__ = ()
        taken_format = results_format.ORDER
        name = _("Instant-Runoff Voting")

        def attrib(self, results):
            blacklisted = set()
            for _i in range(len(results[0])):
                first_places = defaultdict(int)
                for ballot in results:
                    for parti in ballot:
                        if parti not in blacklisted:
                            first_places[parti] += 1
                            break

                total = sum(first_places.values())
                for parti, score in first_places.items():
                    if score > total/2:
                        return [(parti, self.nseats)]
                blacklisted.add(min(first_places, key=first_places.get))
            raise Exception("We should never end up here")

    @listed_attrib
    class Borda(Attribution):
        __slots__ = ()
        taken_format = results_format.ORDER
        name = _("Borda Count")

        def attrib(self, results):
            scores = defaultdict(int)
            for ballot in results:
                for k, parti in enumerate(ballot):
                    scores[parti] += k
            return [(min(scores, key=scores.get), self.nseats)]

    @listed_attrib
    class Condorcet(Attribution):
        """
        This code doesn't support equally-ranked candidates (because the taken format doesn't allow it).
        It also doesn't support incomplete ballots, where not all candidates are ranked.
        """
        __slots__ = ("contingency")
        taken_format = results_format.ORDER
        name = _("Condorcet method")

        class Standoff(Exception): pass

        def __init__(self, *args, contingency=None, **kwargs):
            super().__init__(*args, **kwargs)
            if contingency is not None:
                self.contingency = contingency(*args, **kwargs)

        def attrib(self, results):
            count = defaultdict(int)
            for tup in results:
                for k, parti1 in enumerate(tup):
                    for parti2 in tup[k+1:]:
                        count[parti1, parti2] += 1
                        count[parti2, parti1] -= 1
            win = {}
            for parti, autre in count:
                win[parti] = win.get(parti, True) and (count[parti, autre] > 0)
            for parti in win:
                if win[parti]:
                    return [(parti, self.nseats)]
            if getattr(self, "contingency", None) is None:
                raise Condorcet.Standoff
            return self.contingency.attrib(results)

    @listed_attrib
    class AverageScore(Attribution):
        """
        From a score/rating vote, averages all the scores and elects the one with the best mean.
        """
        __slots__ = ()
        taken_format = results_format.SCORES
        name = _("Score method (average rating)")

        def attrib(self, results):
            # count = defaultdict(int)
            # for parti, tup in results.items():
            #     for score, qty in enumerate(tup):
            #         count[parti] += score * qty

            counts = defaultdict(list)
            for parti, tup in results.items():
                for score, qty in enumerate(tup):
                    counts[parti].extend([score]*qty)

            count = {parti:sum(liz)/len(liz) for parti, liz in counts.items()}

            return [(max(count, key=count.get), self.nseats)]

    @listed_attrib
    class MedianScore(Attribution):
        __slots__ = ("contingency")
        taken_format = results_format.SCORES
        name = _("Majority judgment (median rating)")

        def __init__(self, *args, contingency=AverageScore, **kwargs):
            super().__init__(*args, **kwargs)
            self.contingency = contingency(*args, **kwargs)

        def attrib(self, results):
            counts = defaultdict(list)
            for parti, tup in results.items():
                for score, qty in enumerate(tup):
                    counts[parti].extend([score]*qty)

            counts = {parti : sorted(liz) for parti, liz in counts.items()}

            # ballots not voting for a candidate just do not count for that candidate
            winscore = max(liz[len(liz)//2] for liz in counts.values())
            winners = [parti for parti, liz in counts.items() if liz[len(liz)//2] == winscore]

            if len(winners) <= 1:
                return [(winners[0], self.nseats)]
            # remove the non-winners
            trimmed_results = {parti:tup for parti, tup in results.items() if parti in winners}
            return self.contingency.attrib(trimmed_results)

    class Proportional(Attribution):
        __slots__ = ()
        taken_format = results_format.SIMPLE

    class HondtBase(Proportional):
        __slots__ = ("threshold")
        name = _("Proportional (largest averages)")

        def attrib(self, results):
            if self.threshold:
                results_ = results
                thresh = self.threshold * sum(results.values())
                results = {p:s for p, s in results.items() if s >= thresh}
                if not results:
                    return self.contingency.attrib(results_)

            rv = defaultdict(int)
            for _k in range(self.nseats):
                # compute the ratio each party would get with one more seat
                # take the party with the best ratio
                win = max(results, key=(lambda p:results[p]/(rv[p]+1)))
                rv[win] += 1
            return [(p, s) for p, s in rv.items() if s]

    class HondtNoThreshold(HondtBase):
        __slots__ = ()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.threshold = 0

    class HondtWithThreshold(HondtBase):
        __slots__ = ("contingency")

        def __init__(self, *args, threshold, contingency=HondtNoThreshold, **kwargs):
            super().__init__(*args, **kwargs)
            self.threshold = threshold
            self.contingency = contingency(*args, **kwargs)

    @listed_attrib
    class FakeHondt(HondtBase):
        def __new__(cls, *args, threshold=0, **kwargs):
            if threshold:
                return HondtWithThreshold(threshold=threshold, *args, **kwargs)
            return HondtNoThreshold(*args, **kwargs)

    class SainteLagueBase(Proportional):
        # __slots__ = ("threshold")
        name = _("Proportional (largest averages)")

        threshold = 0 # remove

        def attrib(self, results):
            if self.threshold:
                results_ = results
                thresh = self.threshold * sum(results.values())
                results = {p:s for p, s in results.items() if s >= thresh}
                if not results:
                    return self.contingency.attrib(results_)

            rv = defaultdict(int)
            for _k in range(self.nseats):
                win = max(results, key=(lambda p:results[p]/(rv[p]+.5)))
                rv[win] += 1
            return [(p, s) for p, s in rv.items() if s]

    class Pavia1(Proportional):
        name = _("Proportional (Pavia)")

        def attrib(self, results):

            advantage = {} # benefit of rounding up rather than down
            rv = {}
            for p, votes in results.items():
                fair = votes*self.nseats/sum(results.values()) # nombre juste flottant de sièges
                rv[p] = int(fair)
                down_error = (fair%1)/fair # erreur de l'arrondi vers le bas, proportionnellement au nombre (juste) de sièges
                up_error = (1-(fair%1))/fair # erreur de l'arrondi vers le haut, proportionnellement au nombre (juste) de sièges
                advantage[p] = abs(up_error) - abs(down_error)

            winners = sorted(advantage, key=advantage.get)[:(self.nseats-sum(rv.values()))]
            for p in winners:
                rv[p] += 1

            return rv.items()

    class Pavia2(Proportional):
        """
        A divisor method which seeks to minimize the average error (across all
        states/candidates) between the theoretical floating-point number of
        seats and the apportioned number of seats, relative to the theoretical
        number of seats.
        """

        name = _("Proportional (Pavia)")

        def attrib(self, results):
            fairs = {p : votes*self.nseats/sum(results.values()) for p, votes in results.items()}
            # fair, floating-point number of seats for each party

            def mean_error(party):
                """
                Returns the mean, between all parties, of the error between the
                theoretical number of seats and the apportioned number of
                seats, if `party` were allocated one more seat.
                """
                return fmean(abs(rv[p]+(party==p)-fairs[p])/fairs[p] for p in rv)

            rv = dict.fromkeys(results, 0)
            for _s in range(self.nseats):
                # find the party which would bring the mean error down the most,
                # were it given one more seat
                win = min(results, key=mean_error)
                rv[win] += 1
            return rv.items()

    class Pavia3(Proportional):
        """
        A divisor method which seeks to minimize the average error (across all
        states/candidates) between the theoretical floating-point number of
        seats and the apportioned number of seats, relative to the theoretical
        number of seats.
        """

        name = _("Proportional (Pavia)")

        def attrib(self, results):
            shares = {p : votes/sum(results.values()) for p, votes in results.items()}
            # share, percentage of the vote received by each party

            def relative_error(party, offset=0):
                """
                Returns the relative error, normalized by the fair number of
                seats, of the `party`, if it had `offset` more seats.
                """
                return abs((rv[party]+offset)/self.nseats - shares[party]) / shares[party]

            def relative_error_net_gain(party):
                """
                Returns the gain/loss of relative error if `party` were
                allocated one more seat.
                """
                return relative_error(party, 1) - relative_error(party)

            rv = dict.fromkeys(results, 0)
            for _s in range(self.nseats):
                # find the party which would bring the mean error down the most,
                # were it given one more seat
                win = min(results, key=relative_error_net_gain)
                rv[win] += 1
            return rv.items()

    class Pavia4(Proportional):
        """
        A divisor method which seeks to minimize the average error (across all
        states/candidates) between the theoretical floating-point number of
        seats and the apportioned number of seats, relative to the theoretical
        number of seats.
        """
        """
        Here is a more optimized version.
        """

        name = _("Proportional (Pavia)")

        def attrib(self, results):
            shares = {p : votes/sum(results.values()) for p, votes in results.items()}
            # share, percentage of the vote received by each party

            def relative_error(party, offset=0):
                """
                Returns the relative error, normalized by the fair number of
                seats, of the `party`, if it had `offset` more seats.
                """
                share = shares[party]
                return abs((rv[party]+offset)/self.nseats - share) / share

            relative_cache = _dict() # party -> relative net error gain
            def relative_error_net_gain(party):
                """
                Returns the gain/loss of relative error if `party` were
                allocated one more seat.
                """
                ret = relative_cache.get(party, None)
                if ret is None:
                    ret = relative_error(party, 1) - relative_error(party)
                    relative_cache[party] = ret
                return ret

            rv = _dict.fromkeys(results, 0)
            for _s in range(self.nseats):
                # find the party such that giving it one more seat would bring
                # the mean error down the most
                win = min(results, key=relative_error_net_gain)
                del relative_cache[win]
                rv[win] += 1
            return rv.items()

    Pavia = Pavia4

    class HareBase(Proportional):
        __slots__ = ("threshold")
        name = _("Proportional (largest remainder)")

        def attrib(self, results):
            if self.threshold:
                results_ = results
                thresh = self.threshold * sum(results.values())
                results = {p:s for p, s in results.items() if s >= thresh}
                if not results:
                    return self.contingency.attrib(results_)

            rv = {parti : int(self.nseats*score/sum(results.values())) for parti, score in results.items()}
            winners = sorted(results, key=(lambda p:self.nseats*results[p]/sum(results.values())%1), reverse=True)
            for win in winners[:self.nseats-sum(rv.values())]:
                rv[win] += 1
            return [(p, s) for p, s in rv.items() if s]

    class HareNoThreshold(HareBase):
        __slots__ = ()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.threshold = 0

    class HareWithThreshold(HareBase):
        __slots__ = ("contingency")

        def __init__(self, *args, threshold, contingency=HareNoThreshold, **kwargs):
            super().__init__(*args, **kwargs)
            self.threshold = threshold
            self.contingency = contingency(*args, **kwargs)

    @listed_attrib
    class FakeHare(HareBase):
        def __new__(cls, *args, threshold=0, **kwargs):
            if threshold:
                return HareWithThreshold(threshold=threshold, *args, **kwargs)
            return HareNoThreshold(*args, **kwargs)

    @listed_attrib
    class Randomize(Attribution):
        """
        Everyone votes for their favorite candidate, then one ballot (per seat to fill) is selected at random.
        """
        __slots__ = ()
        taken_format = results_format.SIMPLE
        name = _("Random Allotment")

        def attrib(self, results):
            rd = defaultdict(int)
            for seat in range(self.nseats):
                rd[self.randomobj.choices(tuple(results), results.values())[0]] += 1
            return list(rd.items())

    # faire un vrai tirage au sort parmi la population

init python:
    from collections import namedtuple

    class ElectionMethod(namedtuple("ElectionMethod", ("voting_method", "attribution_method"))):
        def election(self, *args, **kwargs):
            return self.attribution_method.attrib(self.voting_method.vote(*args, **kwargs))

init python:
    def is_subclass(a, b, /):
        return isinstance(a, type) and issubclass(a, b)

    def test_proportionals(it=1000):
        random = renpy.random.Random()
        alpha = 'abcdefghijklmnopqrstuvwxyz'
        solutions = 0
        for _k in range(it):
        # while solutions < 5:
            votes = {l : random.randrange(1000, 100000) for l in alpha[:random.randrange(2, 20)]}
            nseats = random.randrange(10, 100)
            # votes = dict(A=21878, B=9713, C=4167, D=3252, E=1065)
            # nseats = 43
            sumvotes = sum(votes.values())

            meandev = {}
            maxdev = {}
            results = {}
            rtemplate = dict.fromkeys(votes, 0)
            for Attrib in (FakeHondt, SainteLagueBase, FakeHare, Pavia):
                result = dict(Attrib(nseats).attrib(votes))
                meandev[Attrib] = fmean(abs(result.get(p, 0)-(j:=votes[p]*nseats/sumvotes))/j for p in votes)
                maxdev[Attrib] = max(abs(result.get(p, 0)-(j:=votes[p]*nseats/sumvotes))/j for p in votes)
                results[Attrib] = rtemplate | result

            # if min(meandev, key=meandev.get) != SainteLagueBase:
            # if (meandev[FakeHare] != meandev[Pavia]) or (meandev[SainteLagueBase] != meandev[Pavia]) or (maxdev[FakeHare] != maxdev[Pavia]) or (maxdev[SainteLagueBase] != maxdev[Pavia]):
            # if (meandev[SainteLagueBase] != meandev[Pavia]) or (maxdev[SainteLagueBase] != maxdev[Pavia]):
            if results[SainteLagueBase] != results[Pavia]:
                solutions += 1
                print("Found solution:")
                # if meandev[FakeHondt] < meandev[SainteLagueBase]:
                #     print("UNEXPECTED : FakeHondt is better than SainteLague")
                # if meandev[FakeHare] < meandev[SainteLagueBase]:
                #     print("UNEXPECTED : FakeHare is better than SainteLague")
                # if meandev[FakeHare] < meandev[FakeHondt]:
                #     print("UNEXPECTED : FakeHare is better than FakeHondt")
                if meandev[Pavia] != min(meandev.values()):
                    print("UNEXPECTED : Pavia is worse than other methods, in the sum metric")
                # print(f"votes={dict(sorted(votes.items(), key=votes.get, reverse=True))}")
                # if maxdev[Pavia] > maxdev[FakeHare]:
                #     print("UNEXPECTED : Pavia is worse than Hare")
                # if maxdev[Pavia] > maxdev[SainteLagueBase]:
                #     print("UNEXPECTED : Pavia is worse than SainteLague")
                if maxdev[Pavia] != min(maxdev.values()):
                    print("UNEXPECTED : Pavia is worse than other methods, in the max metric")
                print(f"{votes=}")
                print(f"{results=}")
                print(f"{meandev=}")
                print(f"{maxdev=}")

            if solutions >= 5:
                break
        print(f"{solutions=}")

    def test_monotonicity(Attrib):
        random = renpy.random.Random()
        alpha = 'abcdefghijklmnopqrstuvwxyz'

        votes = {l : random.randrange(1000, 100000) for l in alpha[:random.randrange(2, 20)]}
        former_result = {}
        for nseats in range(1, 2000):
            if not (nseats % 100):
                print(f"{nseats=}")
            result = dict(Attrib(nseats).attrib(votes))
            for party in votes:
                if result.get(party, 0) < former_result.get(party, 0):
                    print(f"{Attrib} is not monotonic")
                    print(f"{votes=}")
                    print(f"For {nseats} seats, {result=}")
                    print(f"For {nseats-1} seats, {former_result=}")
                    return
            former_result = result
        print(f"{Attrib} is (probably) monotonic")

    from math import ceil

    def test_quota(Attrib):
        random = renpy.random.Random()
        alpha = 'abcdefghijklmnopqrstuvwxyz'

        votes = {l : random.randrange(1000, 100000) for l in alpha[:random.randrange(2, 20)]}
        allvotes = sum(votes.values())
        lower = upper = True
        for nseats in range(1, 2000):
            if not (nseats % 100):
                print(f"{nseats=}")
            result = dict(Attrib(nseats).attrib(votes))
            for party in votes:
                if lower and (result.get(party, 0) < int(votes[party]*nseats/allvotes)):
                    lower = False
                    print(f"{Attrib=} violates lower quota rule")
                    print(f"{votes=}")
                    print(f"For {nseats} seats, {result=}")
                if upper and (result.get(party, 0) > ceil(votes[party]*nseats/allvotes)):
                    upper = False
                    print(f"{Attrib=} violates upper quota rule")
                    print(f"{votes=}")
                    print(f"For {nseats} seats, {result=}")
                    print(f"Party {party} has {votes[party]*nseats/allvotes} fair seats")
                if not (lower or upper):
                    return
        if lower and upper:
            print(f"{Attrib} (probably) respects the quota rule")
