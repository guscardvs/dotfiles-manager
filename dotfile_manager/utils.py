import itertools
import os
import sys
from collections import deque
from collections.abc import Callable, Iterable
from datetime import UTC
from functools import wraps
from itertools import islice
from pathlib import Path
from typing import Literal

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
        self.message = message


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


def merge_dicts(
    left: dict,
    right: dict,
    on_conflict: Literal["strict", "left", "right"],
    merge_sequences: bool = True,
) -> dict:
    """
    Merge two dictionaries with customizable conflict resolution strategy.

    Args:
        left (dict): The left dictionary to merge.
        right (dict): The right dictionary to merge.
        on_conflict (Literal["strict", "left", "right"]): The conflict resolution strategy to use.

            - 'strict': Raise a MergeConflict exception if conflicts occur.
            - 'left': Prioritize the values from the left dictionary in case of conflicts.
            - 'right': Prioritize the values from the right dictionary in case of conflicts.
        merge_sequences (bool, optional): Indicates whether to merge sequences (lists, sets, tuples) or skip them.

            - If True, sequences will be merged based on the conflict resolution strategy.
            - If False, sequences will be skipped, and the value from the chosen (defaults to left on strict)
            dictionary will be used. Default is True.

    Returns:
        dict: The merged dictionary.

    Raises:
        MergeConflict: If conflicts occur and the conflict resolution strategy is set to 'strict'.
    """

    output = {key: value for key, value in left.items() if key not in right}

    stack = deque([(left, right, output)])

    while stack:
        left_curr, right_curr, output_curr = stack.pop()

        for key, value in right_curr.items():
            if key not in left_curr:
                output_curr[key] = value
            elif isinstance(value, list | set | tuple) and merge_sequences:
                left_val = left_curr[key]
                if isinstance(left_val, list | set | tuple):
                    type_ = type(value) if on_conflict == "right" else type(left_val)
                    output_curr[key] = type_(itertools.chain(left_val, value))
            elif isinstance(value, dict):
                if isinstance(left_curr[key], dict):
                    output_curr[key] = {
                        lkey: lvalue
                        for lkey, lvalue in left_curr[key].items()
                        if lkey not in value
                    }
                    stack.append((left_curr[key], value, output_curr[key]))
            elif on_conflict not in ("left", "right"):
                raise ValueError(
                    "Conflict found when trying to merge dicts",
                    key,
                    value,
                    left_curr[key],
                )
            elif on_conflict == "left":
                output_curr[key] = left_curr[key]
            else:
                output_curr[key] = value

    return output


timezone = TimeZone(now().astimezone().tzinfo or UTC)


def get_timezone() -> TimeZone:
    """
    Returns the current timezone.

    Returns:
        TimeZone: The current timezone.
    """
    return timezone
