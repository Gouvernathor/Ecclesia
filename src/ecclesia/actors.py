import abc
from collections import Counter, namedtuple
from collections.abc import Iterable, Sequence
from math import sqrt, hypot, erf, nan as NAN
from typing import ClassVar
from . import _settings

SQ2 = sqrt(2)

def _normal_to_uniform(x, mu, sigma):
    """Converts a normal distribution to a uniform distribution.

    From an x value generated from a normal distribution of mean mu and standard
    deviation sigma, returns a value following a uniform distribution between 0
    and 1 such that the higher the x, the higher the return value.
    """
    return 0.5 * (1 + erf((x - mu) / (sigma * SQ2)))

def get_alignment(opinions, opinmax, factors=None) -> float:
    """Returns the one-dimensional alignment of the opinions.

    Assuming `opinions` follow the nominal constraints with regards to
    `opinmax`, the return value is between 0 and 1.
    The return value is computed such that if each opinion, in each object
    of a pool of HasOpinions instances, is generated randomly following an
    integer uniform distribution, the return value follows a uniform law.
    """

    nopinions = len(opinions)
    if factors is None:
        factors = tuple(1-i/nopinions for i in range(nopinions))

    scapro = sum(opinions[i] * factors[i] for i in range(nopinions))
    ran = range(-opinmax, opinmax+1)
    # standard deviation of one opinion taken solo
    one_sigma = sqrt(sum(i**2 for i in ran) / len(ran))
    # using Lyapunov's central limit theorem
    sigma = hypot(*(one_sigma * fac for fac in factors))

    return _normal_to_uniform(scapro, 0, sigma)

class HasOpinions(abc.ABC):
    """A mixin class for objects that have opinions on subjects."""
    """
    The `nopinions`, `opinmax` and optionally `opinion_alignment_factors` class
    attributes should be global to a given system, and be set once in a base
    subclass for all your classes having opinions.
    (This might get reimplemented differently in a future version.)
    HasOpinions subclasses should definitely not support operations with classes
    with different `nopinions` or `opinmax` values. Using isinstance is advised.
    """

    nopinions: ClassVar[int]
    opinmax: ClassVar[int]
    opinion_alignment_factors: ClassVar[Sequence[float]]

    opinions: Sequence[int]

    def __init__(self, opinions=None, *, randomobj=None, randomkey=None,):
        """
        The main attribute is `opinions`, a sequence of numerical values
        (preferably integers). Each value represents the answer to a closed
        question or affirmation on a certain subject, maximum meaning totally
        agreeing, minimum meaning totally disagreeing, and 0 meaning being
        neutral.
        The length of `opinions` should be `nopinions`, and each value should be
        between -`opinmax` and +`opinmax` (inclusive).
        """
        if opinions is None:
            if randomobj is None:
                randomobj = _settings.Random(randomkey)
            opinions = randomobj.choices(
                range(-self.opinmax, self.opinmax+1),
                k=self.nopinions)
        self.opinions = opinions

    def __xor__(self, other, /):
        """
        Subclasses of HasOpinions are expected to override the `__xor__` method
        (for the `^` operator). It should take other instances of HasOpinions
        and return a value proportional to the disagreement between the two
        objects, the higher the stronger the disagreement.

        The operation should be symmetric : you should add
        ``__rxor__ = __xor__`` in all your subclasses.

        All subclasses of HasOpinions do not have to support disagreement with
        all other subclasses in the same system, or even with other instances of
        the same subclass, but the voting methods rely on the `^` operator being
        supported between the voter and party classes.

        The operation does not have to be symmetric when it comes to types : you
        can have different disagreement values between a voter with opinion o
        and a party with opinion q, than between a voter with opinion q and a
        party with opinion o.
        """
        return NotImplemented

    def get_alignment(self=None, factors=None) -> float:
        if factors is None:
            factors = self.opinion_alignment_factors
        return get_alignment(self.opinions, self.opinmax, factors)


class Vote(namedtuple("Vote", ("votes_for", "votes_against"))):
    """ The results of a binary vote.

    The blank votes are not counted. To calculate a threshold on the whole
    number of members, use ``vote.votes_for / house.nseats``. To calculate the
    threshold on the number of duly elected members, use
    ``vote.votes_for / sum(house.members.values())``.
    """

    __slots__ = ()

    __lt__ = __gt__ = __le__ = __ge__ = lambda self, other: NotImplemented

    def __neg__(self):
        """
        Returns the reverse of the vote, inverting the for/against ratio.
        Simulates a vote on the opposite motion.
        """
        return type(self)(self.votes_against, self.votes_for)

    @property
    def votes_cast(self) -> int:
        return sum(self)

    @property
    def ratio(self) -> float:
        """
        Returns the ratio of votes for over the total of votes cast.
        If there are no votes cast, returns a nan.
        """
        cast = self.votes_cast
        if not cast:
            return NAN
        return self.votes_for / cast

    @staticmethod
    def order(*votes):
        """
        Returns the votes in order of decreasing ratio.
        The ties are ordered by decreasing number of positive votes,
        then by the order they came in.
        """
        return sorted(votes, key=(lambda v:(-v.ratio, -v.votes_for)))


class House:
    """A whole House of Parliament.

    Some constraints :
    - all members have the same voting power
    - staggering is not (yet) supported (that is, when general elections don't
      renew all the seats at once, like in the french or american Senates),
      but subclasses may implement it by overriding the election method and
      subclassing District for example.
    """

    class District:
        """An electoral district relating to a House.

        Several district objects can represent the same territory and have the
        same voter pool, and yet relate to different Houses : this is normal.
        For example, the districts for the US State of Wyoming would be as
        follows :
        - one for the three presidential electors
        - one for the lone federal representative
        - one or possibly two for the two federal senators (depending on implem)
        All three or four of these districts would have the same voter pool, yet
        be different objects because they relate to different Houses, even in
        the case where they would have the same election method.
        """

        def __init__(self,
                    election_method,
                    voterpool: Sequence[HasOpinions],
                    *, identifier=None, nseats=None):
            """
            The `election_method` takes an ElectionMethod instance.
            The `voterpool` parameter takes a sequence (important) of voters,
            each an instance of HasOpinions. They will be used by the
            `election_method`.

            The `identifier` optional parameter is used in the repr and serves
            to identify the districts.

            The `nseats` parameter is optional, intended to be indicative of the
            theoretical number of seats in the district, and allowing a
            theoretical number of seats to be associated to a newly-created
            House before it is first populated.
            If not provided, it is sought in the attribution method of the
            election method. Most implementations should rely on that behavior,
            however keep in mind that some election methods do not have one
            accessible attribution method, and that attribution methods do not
            have to have a constant number of seats.
            """
            self.election_method = election_method
            self.voterpool = voterpool
            self.identifier = identifier

            if nseats is None:
                try:
                    nseats = election_method.attribution_method.nseats
                except AttributeError:
                    pass
            self.nseats = nseats

        def election(self) -> Counter[HasOpinions, int]:
            return self.election_method.election(self.voterpool)

        def __repr__(self):
            identifier = self.identifier
            if identifier is None:
                return super().__repr__()
            return f"<{type(self).__name__} {self.identifier!r}>"

    def __init__(self,
                districts: Iterable[District]|dict[District, Counter[HasOpinions, int]],
                *, name=None, majority=.5):
        """
        `districts` may either be an iterable of district instances, if the
        House is created empty, but it can also be a dict linking each district
        to a Counter of already attributed seats.
        You can create a partiless House with individual members, by passing
        ``Counter(district_members_lists)`` as a value for each district, but it
        is intended that the Counters' keys be parties with indistinct members.

        `name` is only used in the repr.
        `majority` is used in the `vote` method.
        """
        if not isinstance(districts, dict):
            districts = {d: Counter() for d in districts}
        self.districts = districts

        self.name = name
        self.majority = majority

    @property
    def members(self) -> Counter[HasOpinions, int]:
        """
        Returns a Counter linking each party to the number of seats it holds,
        regardless of the district.

        Takes some time to be computed, so this may be cached in a subclass.
        For the list (with repetitions) of the individual members, use the
        `members.elements()` method.
        """
        rv = Counter()
        for dmembers in self.districts.values():
            rv += dmembers
        return rv

    @property
    def nseats(self) -> int|None:
        """
        If all districts support providing a theoretical number of seats,
        returns the total. Otherwise, returns None.
        """
        rv = 0
        for d in self.districts:
            dnseats = d.nseats
            if dnseats is None:
                return None
            rv += dnseats
        return rv

    def election(self) -> Counter[HasOpinions, int]:
        """Triggers an election in each electoral district, returns the `members` result."""
        rv = Counter()
        for district in tuple(self.districts):
            self.districts[district] = district.election()
            rv += self.districts[district]
        return rv

    def vote(self, ho: HasOpinions) -> Vote:
        """Returns the result of a vote on `ho`.

        `ho` may be a motion or bill, but also a person to elect or confirm.
        """
        votes_for = 0
        votes_against = 0
        for party, nseats in self.members.items():
            disag = ho ^ party
            if disag > 0:
                votes_for += nseats
            elif disag < 0:
                votes_against += nseats
        return Vote(votes_for, votes_against)

    def __repr__(self):
        name = self.name
        if name is None:
            return super().__repr__()
        return f"<{type(self).__name__} {self.name!r}>"
