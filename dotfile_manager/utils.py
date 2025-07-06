import itertools
import os
import sys
from collections import deque
from collections.abc import Callable, Hashable, Iterable
from datetime import UTC
from functools import wraps
from itertools import islice
from pathlib import Path
from typing import Any, Literal

from escudeiro.data import data, field
from escudeiro.misc import TimeZone, lazymethod, now
from termcolor import colored

LOOKUPS_MAX_SIZE = 10  # Maximum number of lookups allowed for a PartialEntry


@data(frozen=False)
class PartialEntry:
    """Represents a partial entry in the manifest.
    This is used to define a location with optional lookups that can be applied
    to it. For example, the name could be "bash" and the lookups could be
    ("/usr/bin", "/bin", "/usr/local/bin", "~/.local/bin").
    The lookups are applied in order, and the first one that exists is used.
        for lookup in self.lookups:
            result = f"{lookup}/{result}" if lookup else result
        return result
    """

    name: str
    lookups: Iterable[Path] = field(default=(), fromdict=tuple)

    def __post_init__(self):
        """
        Initializes the PartialEntry instance.
        Converts lookups to Path objects if they are not already.
        """
        # Ensure lookups are materialized to avoid infinite evaluation
        self.lookups = tuple(islice(self.lookups, LOOKUPS_MAX_SIZE))

    @lazymethod
    def make(self) -> str:
        """
        Returns the location with the lookups applied.
        """
        if not self.lookups:
            return self.name
        for lookup in self.lookups:
            result = lookup / self.name
            if result.exists():
                return str(result)
        return self.name

    def __str__(self) -> str:
        """
        Returns the string representation of the partial entry.
        """
        return self.make()

    def is_valid(self) -> bool:
        """
        Checks if the partial entry is valid.
        A partial entry is valid if the path it resolves to exists.
        Returns:
            bool: True if the path exists, False otherwise.
        """
        return Path(self.make()).exists()


def configdir():
    match os.name:
        case "posix":
            return Path.home() / ".config/dfman"
        case _:
            raise ValidationError(f"Unsupported OS: {os.name}")


class ValidationError(Exception):
    """
    Custom exception for validation errors.
    This is used to indicate that a validation error has occurred.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message: str = message


def handle_error[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to handle errors in a function.
    It catches exceptions and prints an error message.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(colored(e.message, "red"))
            sys.exit(1)
        except NotImplementedError:
            print(colored("This feature is not implemented yet.", "yellow"))
            print(
                colored(
                    "Please open an issue on GitHub to request this feature.", "yellow"
                )
            )
            sys.exit(1)

    return wrapper


def load_path(loc: str | Path, home: Path | None = None) -> Path:
    """
    Converts a string or Path to a Path object, expanding user directories.
    If the path is relative, it resolves it against the home directory.

    Args:
        loc (str | Path): The location to convert.
        home (Path | None): The home directory to resolve relative paths against.

    Returns:
        (Path): The resolved Path object.
    """
    if home is None:
        home = Path.home()
    path = Path(loc).expanduser()
    if not path.is_absolute():
        path = home / path
    return path


timezone = TimeZone(now().astimezone().tzinfo or UTC)


def get_timezone() -> TimeZone:
    """
    Returns the current timezone.

    Returns:
        TimeZone: The current timezone.
    """
    return timezone
