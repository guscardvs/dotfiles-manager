from enum import auto
from typing import override

from escudeiro.misc import KebabEnum, ValueEnum


class ManifestFormat(ValueEnum, KebabEnum):
    """
    Enum representing the format of the manifest.
    """

    JSON = auto()
    YAML = auto()
    TOML = auto()
    PRESUMED = auto()
    YML = YAML

    @override
    @classmethod
    def _missing_(cls, value: object) -> "ManifestFormat":
        return super()._missing_(value) or cls.PRESUMED

    @classmethod
    def valid(cls) -> tuple["ManifestFormat", ...]:
        """
        Returns a tuple of valid manifest formats (excluding PRESUMED).
        """
        return tuple(fmt for fmt in cls if fmt is not cls.PRESUMED)
