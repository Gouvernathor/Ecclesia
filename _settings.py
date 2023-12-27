from random import Random as _Random

def set_random(Random_=_Random, /, *, reset_electrobj=True):
    """Sets the random type used by the game.

    Defaults to the python standard random module.
    Can be passed any type supporting the random.Random class interface.

    By default, also resets the common random object used by voting methods
    to an instance of the new type.
    If `reset_electrobj` is specifically False, the reset does not happen.
    Otherwise, if `reset_electrobj` is not True, it is used as the seed for the
    new random object.
    """
    global Random
    global electrobj
    Random = Random_
    if reset_electrobj is not False:
        if reset_electrobj is True:
            reset_electrobj = None
        set_electrobj(Random_(reset_electrobj))

def set_electrobj(electrobj_, /):
    """Sets the random object used by the voting methods."""
    global electrobj
    electrobj = electrobj_

set_random()
