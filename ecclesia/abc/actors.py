import abc
from collections.abc import Sequence
from math import erf, hypot, sqrt
import random
from typing import ClassVar

__all__ = ("get_alignment", "HasOpinions")

SQ2 = sqrt(2)

def _normal_to_uniform(x: float, mu: float, sigma: float):
    """Converts a normal distribution to a uniform distribution.

    From an x value generated from a normal distribution of mean mu and standard
    deviation sigma, returns a value following a uniform distribution between 0
    and 1 such that the higher the x, the higher the return value.
    (This function is here so that the code can be checked by stats people.)
    """
    return 0.5 * (1 + erf((x - mu) / (sigma * SQ2)))

def get_alignment(
        opinions: Sequence[int],
        opinmax: int,
        factors: Sequence[float]|None = None,
        ) -> float:
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

    This typically covers voters, parties, and bills.

    The `nopinions`, `opinmax` and optionally `opinion_alignment_factors` class
    attributes should be global to a given system, and be set once in an
    abstract subclass of HasOpinions that will be a base class for all your
    classes having opinions.
    In any case, HasOpinions subclasses should definitely not support operations
    between subclasses with different `nopinions` or `opinmax` values.

    The opinions of someone or something are represented as a multidimentional
    vector of integers, with each dimension representing one subject.
    The value for each dimension can be symmetrically positive or negative.
    Values close to 0 represent neutrality or uncertainty. There are `nopinions`
    dimensions, and each value is between -`opinmax` and +`opinmax` (inclusive).

    If no opinions sequence is provided to the constructor, the opinions are
    generated following an integral uniform law for each dimension. The optional
    `randomobj` parameter can be used to provide a random object (following the
    random.Random class specification) to generate the opinions, or a
    `randomseed` to deterministically seed a new random object.

    Finally, the objects having an opinion (typically, voters and parties) can
    be placed along a left-wing-right-wing-type axis, called the alignment.
    The `opinion_alignment_factors` attribute provides a sequence of ponderation
    factors for each dimension of the opinion vector. It is computed as
    described in its own function.
    """

    # TODO: consider having a -1 to +1 float (or Fraction) for each dimension, and ditch opinmax
    # but float would reduce precision and Fraction would reduce performance

    nopinions: ClassVar[int]
    opinmax: ClassVar[int]
    opinion_alignment_factors: ClassVar[Sequence[float]]

    opinions: Sequence[int]

    def __init__(self, opinions: Sequence[int]|None = None, *,
            randomobj: random.Random|None = None,
            randomseed=None,
            ):
        if opinions is None:
            if randomobj is None:
                randomobj = random.Random(randomseed)
            opinions = randomobj.choices(
                range(-self.opinmax, self.opinmax+1),
                k=self.nopinions)
        self.opinions = opinions

    def __xor__(self, other, /) -> float:
        """
        Subclasses of HasOpinions are expected to override the `__xor__` method
        (for the `^` operator). It should take other instances of HasOpinions -
        or, if you read the class's docstring, of your own abstract base
        subclass of HasOpinions - and return a value proportional to the
        disagreement between the two objects, the higher the stronger the
        disagreement.

        All (concrete) subclasses do not have to support disagreement with
        all other subclasses in the same system, or even with other instances of
        the same subclass, but the voting methods rely on the `^` operator being
        supported at least between the voter class and the party class.

        The operation should be symmetric : you should add
        ``__rxor__ = __xor__`` in all your subclasses.

        However, the operation does not have to be symmetric when it comes to
        types : you can have different disagreement values between a voter with
        opinion o and a party with opinion q, than between a voter with opinion
        q and a party with opinion o.
        """
        return NotImplemented

    def get_alignment(self, factors: Sequence[float]|None = None) -> float:
        """
        This offers the ability to override the factors used for the alignment.
        Other parameters to the get_alignment function are pre-filled.
        """
        if factors is None:
            factors = self.opinion_alignment_factors
        return get_alignment(self.opinions, self.opinmax, factors)
