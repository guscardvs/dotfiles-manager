def no_color(msg: str, color: str) -> None:
    _ = color  # Unused
    print(msg)


def pytest_sessionstart() -> None:
    """Hook to configure settings before tests run."""
    utils = __import__("dotfile_manager.utils", fromlist=["print_colored"])
    utils.print_colored = no_color
