# CLAUDE.md

## Project

`rsl` - CLI tool for managing Resilio Sync folders via the undocumented web UI API (`/gui/`).

PEP 723 script (`main.py`) with `uv_build` packaging for distribution.

- `main.py` - standalone script with PEP 723 metadata + all logic
- `src/rsl/__init__.py` - re-exports `main` for package distribution
- `src/rsl/main.py` - symlink to `../../main.py`

Run standalone: `./main.py <args>` or `uv run --script main.py <args>`
Install: `uvx --from git+https://github.com/pythoninthegrass/rsl.git rsl <args>`

## Servers

Two Resilio Sync instances configured via `RSL_SRC_*` and `RSL_DST_*` env vars:

- **src**: Synology NAS, base path `/volume1/shares`
- **dst**: Linux server, base path `/media/shares`

## Usage

```bash
rsl list                        # show folders on both servers
rsl src list                    # show folders on src only
rsl dst list                    # show folders on dst only
rsl <server> add <name|path>    # add folder as new sync folder
rsl <server> connect <name>     # connect disconnected folder (uses base_path/name)
rsl <server> connect-all        # connect all disconnected folders
rsl <server> remove <name>      # remove sync folder
rsl <server> set-pref <key> <value>
                                # set preference on all folders
rsl <server> set-pref <name> <key> <value>
                                # set preference on one folder
```

Mutation commands (`add`, `connect`, `connect-all`, `remove`, `set-pref`) require an explicit server.
`list` defaults to all servers when no server is specified.

Name arguments resolve to `base_path/name`. Paths starting with `/` are used as-is.

## Architecture

- `ResilioAPI` class wraps the internal web UI API (not the official `/api/v2/`)
- `ResilioAPI(name)` takes a server name (`src` or `dst`) and reads `RSL_{NAME}_*` env vars
- Auth: HTTP Basic Auth + CSRF token from `/gui/token.html`
- Config via `python-decouple`: reads `.env` file or environment variables
- Self-signed TLS cert on Resilio requires disabled SSL verification

## Configuration

- Env vars in `.env` (see `.env.example` for template)
- Resilio Sync runs as a user service on dst: `systemctl --user status resilio-sync`
- Resilio Sync config on dst: `~/.config/resilio-sync/config.json`
- Resilio Sync storage/DB on dst: `~/.config/resilio-sync/storage/`

### Synology (src) permissions

Resilio Sync runs as `rslsync` user. New shared folders need an explicit ACL grant for `rslsync` before Resilio can sync them (Synology ACLs override POSIX permissions).

```bash
sudo synoacltool -add /volume1/shares/<folder> user:rslsync:allow:rwxpdDaARWcCo:fd--
```

Or via DSM web UI: Control Panel > Shared Folder > Edit > Permissions tab > "System internal user" dropdown > tick Read/Write for `rslsync`.

### API endpoints discovered by reverse-engineering the web UI JS

- `getsyncfolders` (with `discovery=1`) - list connected folders
- `getdisconnectedfolders` - list folders shared by identity but not connected locally
- `adddisconnectedfolder` - connect a disconnected folder (`folderid`, `path`, `selectivesync`, `force`)
- `addsyncfolder` - add a new folder by path
- `removefolder` - remove a folder
- `setfolderpref` - set folder preferences

## Linting

```bash
ruff format --check --diff .
ruff format .
ruff check .
```

## Dependencies

Runtime: `uv`

Development: `mise install` (installs python, ruff, uv from `.tool-versions`)

## Context7 Libraries

- astral-sh/ruff
- astral-sh/uv
- encode/httpx
- hbnetwork/python-decouple
- websites/help_resilio_hc_en-us
