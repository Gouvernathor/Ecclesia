from typing import NewType

from ..actors import HasOpinions

__all__ = ()

Voter = NewType("Voter", HasOpinions)
Party = NewType("Party", HasOpinions)
