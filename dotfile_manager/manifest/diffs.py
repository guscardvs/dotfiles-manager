from pathlib import Path

from termcolor import colored

from dotfile_manager.manifest.loader import dumpers
from dotfile_manager.manifest.schema import Dotfile, Manifest


def diff_manifest(left: Manifest, right: Manifest) -> tuple[Manifest, bool]:
    """Compare two Manifest objects and return the one that is different.
    If they are equal, return the left one and False.
    Args:
        left: The base Manifest object to compare.
        right: The Manifest object to compare against.
    Returns:
        A tuple containing the updated Manifest object and a boolean indicating
        if right is different from left.
    If they are equal, returns (left, False).
    If they are different, returns (right, True).
    """
    return (left, False) if manifest_is_equal(left, right) else (right, True)


def manifest_is_equal(left: Manifest, right: Manifest) -> bool:
    """
    Check if two Manifest objects are equal based on their attributes.
    Args:
        left: The first Manifest object.
        right: The second Manifest object.
    Returns:
        True if the Manifest objects are equal, False otherwise.
    """
    return (
        left.root == right.root
        and left.repository_url == right.repository_url
        and left.original_format == right.original_format
        and set(left.extra_paths) == set(right.extra_paths)
        and left.default_terminal == right.default_terminal
        and left.default_editor == right.default_editor
        and left.default_shell == right.default_shell
        and left.repository_branch == right.repository_branch
        and dotfiles_are_equal(left.dotfiles, right.dotfiles)
        and left.pinned_hash == right.pinned_hash
    )


def dotfiles_are_equal(left: list[Dotfile], right: list[Dotfile]) -> bool:
    """
    Check if two lists of Dotfile objects are equal.
    Args:
        left: The first list of Dotfile objects.
        right: The second list of Dotfile objects.

    Returns:
        True if both lists contain the same Dotfile objects, False otherwise.
    """
    if len(left) != len(right):
        return False
    return all(
        dotfile_is_equal(left_dotfile, right_dotfile)
        for left_dotfile, right_dotfile in zip(left, right)
    )


def dotfile_is_equal(left: Dotfile, right: Dotfile) -> bool:
    """
    Check if two Dotfile objects are equal based on their attributes.
    Args:
        left: The first Dotfile object.
        right: The second Dotfile object.

    Returns:
        True if the Dotfile objects are equal, False otherwise.
    """
    return (
        left.name == right.name
        and left.location == right.location
        and left.dflocation == right.dflocation
        and left.description == right.description
    )


def persist_changes(manifest: Manifest, source: Path):
    """
    Persist changes to the manifest by writing it to the source path.

    Args:
        manifest (Manifest): The manifest to persist.
        source (Path): The manifest path.
    """
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)

    source.write_text(dumpers[manifest.original_format](manifest))
    print(colored(f"Manifest file {source} updated.", "yellow"))
