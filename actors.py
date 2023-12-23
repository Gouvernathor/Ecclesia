import abc
from collections.abc import Sequence
from math import sqrt, hypot, erf
import random # TODO: make parameterizable
from typing import ClassVar

SQ2 = sqrt(2)

def _normal_to_uniform(x, mu, sigma):
    """Converts a normal distribution to a uniform distribution.

    From an x value generated from a normal distribution of mean mu and standard
    deviation sigma, returns a value following a uniform distribution between 0
    and 1 such that the higher the x, the higher the return value.
    """
    return 0.5 * (1 + erf((x - mu) / (sigma * SQ2)))

def get_alignment(opinions, opinmax, factors=None):
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
    """A mixin class for objects that have opinions on subjects.

    The main attribute is `opinions`, a sequence of numerical values (preferably
    integers). Each value represents the answer to a closed question or
    affirmation on a certain subject, maximum meaning totally agreeing, minimum
    meaning totally disagreeing, and 0 meaning being neutral.
    The length of `opinions` is `nopinions`, and each value is between
    -`opinmax` and +`opinmax` (inclusive).

    Subclasses of HasOpinions are supposed to override the `__xor__` method
    (for the `^` operator). It should take other instances of HasOpinions and
    return a value proportional to the disagreement between the two objects, the
    higher the stronger the disagreement.
    The operation should be symmetric : you should add ``__rxor__ = __xor__``
    in all your subclasses.
    All subclasses of HasOpinions do not have to support disagreement with all
    other subclasses in the same system, but the voting methods rely on the
    `^` operator being supported between the voter and party classes.
    The operation does not have to be symmetric when it comes to types : you can
    have different disagreement values between a voter with opinion o and a
    party with opinion q, than between a voter with opinion q and a party with
    opinion o.

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

    def __init__(self, opinions=None, *,
            randomobj=None,
            randomkey=None,
            ):
        if opinions is None:
            if randomobj is None:
                randomobj = random.Random(randomkey)
            opinions = randomobj.choices(range(-self.opinmax, self.opinmax+1), k=self.nopinions)

        self.opinions = opinions

    def __xor__(self, other, /):
        return NotImplemented

    def get_alignment(self=None, factors=None):
        if factors is None:
            factors = self.opinion_alignment_factors
        return get_alignment(self.opinions, self.opinmax, factors)
