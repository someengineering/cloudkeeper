from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class RandomConfig:
    kind: ClassVar[str] = "random"
    seed: int = field(default=0, metadata={"description": "Random seed"})
    size: float = field(
        default=1.0, metadata={"description": "Exponential cloud size multiplier (0.5 - 2.0 are reasonable values)"}
    )
