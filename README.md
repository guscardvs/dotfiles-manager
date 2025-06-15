# Dotfile Manager

A flexible, Python-based tool for managing, synchronizing, and linking your dotfiles across systems using a manifest-driven approach.

## Features

- **Manifest-based configuration**: Supports TOML, YAML, and JSON formats.
- **Git integration**: Synchronize dotfiles with remote repositories.
- **Automatic linking**: Create symlinks for dotfiles as specified in the manifest.
- **System import**: Generate manifests from your current dotfiles.
- **Customizable**: Easily extendable and configurable.

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/yourusername/dotfile-manager.git
cd dotfile-manager
pip install -e .
```

## Usage

All commands are available via the CLI app:

```bash
python -m dotfile-manager <command> [options]
```

### Common Commands

- **Check manifest:**
    ```bash
    python -m dotfile-manager check-settings --manifest-path <path>
    ```
- **Sync with remote:**
    ```bash
    python -m dotfile-manager sync
    ```
- **Review repository status:**
    ```bash
    python -m dotfile-manager review
    ```
- **Link dotfiles:**
    ```bash
    python -m dotfile-manager link
    ```
- **Import from system:**
    ```bash
    python -m dotfile-manager from-system
    ```
- **Download dotfiles from remote:**
    ```bash
    python -m dotfile-manager download --repository-url <url>
    ```

## Manifest Example

```toml
[dotfile_manager]
root = "~/dotfiles"
repository_url = "git@github.com:yourusername/dotfiles.git"
repository_branch = "main"
dotfiles = [
    { name = ".bashrc", location = "~/.bashrc" },
    { name = ".vimrc", location = "~/.vimrc" }
]
```

## Project Structure

```
dotfile_manager/
        app.py          # CLI entrypoint
        utils.py        # Utilities and helpers
        linker/         # Symlink logic
        manifest/       # Manifest schema, loader, and format logic
        syncer/         # Git integration
```

## Requirements

- Python 3.13+
- [escudeiro](https://guscardvs.github.com/escudeiro)
- [gitpython](https://gitpython.readthedocs.io/)
- [termcolor](https://pypi.org/project/termcolor/)
- [ruamel.yaml](https://pypi.org/project/ruamel.yaml/)
- [tomlkit](https://pypi.org/project/tomlkit/)
- [orjson](https://pypi.org/project/orjson/)
- [cyclopts](https://pypi.org/project/cyclopts/)

## License

Apache License

---

*Contributions welcome! Send your pull requests.*