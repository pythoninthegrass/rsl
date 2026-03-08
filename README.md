# rsl

CLI tool for managing [Resilio Sync](https://www.resilio.com/sync/)
folders via the undocumented web UI API.

Supports multiple servers configured via environment variables.
Enables CRUD operations on sync folders without logging into
the web console on each server.

## Minimum Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Recommended Requirements

- [mise](https://mise.jdx.dev/getting-started.html)

## Install

### Standalone (no install)

Copy `main.py` to the target machine and run directly.
Dependencies are resolved automatically by `uv` via
[PEP 723](https://peps.python.org/pep-0723/) inline metadata.

```bash
# Run from the repo
./main.py list

# Or explicitly with uv
uv run --script main.py list

# Deploy to a remote host
scp main.py user@host:~/.local/bin/rsl
```

### Install from git

```bash
# One-off execution
uvx --from git+https://github.com/pythoninthegrass/rsl.git rsl list

# Persistent install
uv tool install git+https://github.com/pythoninthegrass/rsl.git
rsl list
```

## Configuration

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

Alternately export or run inline environment variables:

```bash
# export
export RSL_SRC_HOST=syn
export RSL_SRC_PORT=28888
rsl src list

# inline
RSL_SRC_HOST=syn RSL_SRC_PORT=28888 rsl src list
```

Environment variables (per server, replace `<SRV>` with `SRC` or `DST`):

| Variable | Default | Description |
| --- | --- | --- |
| `RSL_<SRV>_HOST` | `localhost` | Resilio host |
| `RSL_<SRV>_PORT` | `8888` | Resilio port |
| `RSL_<SRV>_USER` | `admin` | Web UI username |
| `RSL_<SRV>_PASS` | *(required)* | Web UI password |
| `RSL_<SRV>_BASE_PATH` | `/media/shares` | Base path for folders |

## Quickstart

```bash
# List folders on all servers
rsl list

# List folders on a specific server
rsl src list

# Add a folder by name (resolves to base_path/name)
rsl src add Books

# Add a folder by absolute path
rsl src add /volume1/shares/Books

# Connect a disconnected folder
rsl dst connect Books

# Connect all disconnected folders
rsl dst connect-all

# Remove a sync folder
rsl src remove Books

# Set a preference on one folder
rsl src set-pref Books selectivesync true

# Set a preference on all folders
rsl src set-pref selectivesync true
```

Mutation commands (`add`, `connect`, `connect-all`, `remove`,
`set-pref`) require an explicit server.
`list` defaults to all servers when no server is specified.

Name arguments resolve to `base_path/name`. Paths starting with `/` are used as-is.

## Development

```bash
# Install python, ruff, and uv via mise
mise install

# Install project dependencies
uv sync --all-extras

# Lint
ruff format --check --diff .
ruff check .

# Format
ruff format .
```

## Project Structure

```text
main.py                  # PEP 723 standalone script + all logic
src/rsl/__init__.py      # Re-exports main for package distribution
src/rsl/main.py          # Symlink to ../../main.py
pyproject.toml           # uv_build backend + entry point
.tool-versions           # mise runtime versions (python, ruff, uv)
.env.example             # Environment variable template
```
