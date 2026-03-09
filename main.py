#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "httpx>=0.28.1,<1.0",
#     "python-decouple>=3.8",
# ]
# [tool.uv]
# exclude-newer = "2026-03-31T00:00:00Z"
# ///

"""
Manage Resilio Sync folders via the web UI API.

Supports multiple servers (src, dst) configured via environment variables.

Usage:
    rsl list                      Show folders on all servers
    rsl src list                  Show folders on src server only
    rsl dst list                  Show folders on dst server only
    rsl <server> add <name|path>  Add folder as new sync folder
    rsl <server> connect <name> [path]
                                  Connect folder on specified server
    rsl <server> connect-all      Connect all disconnected folders on server
    rsl <server> remove <name>    Remove sync folder
    rsl <server> set-pref <key> <value>
                                  Set preference on all folders
    rsl <server> set-pref <name> <key> <value>
                                  Set preference on one folder
    rsl <server> set-setting <key> <value>
                                  Set global power user preference

Environment (per server, replace <SRV> with SRC or DST):
    RSL_<SRV>_HOST       Resilio host (default: localhost)
    RSL_<SRV>_PORT       Resilio port (default: 8888)
    RSL_<SRV>_USER       Web UI username (default: admin)
    RSL_<SRV>_PASS       Web UI password (required)
    RSL_<SRV>_BASE_PATH  Base path for folders (default: /media/shares)
"""

import httpx
import re
import ssl
import sys
from pathlib import Path
from urllib.parse import quote

SERVERS = ("src", "dst")


def _decouple_config():
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        from decouple import Config, RepositoryEnv

        return Config(RepositoryEnv(env_file))
    else:
        from decouple import config

        return config


class ResilioAPI:
    def __init__(self, name: str):
        config = _decouple_config()
        prefix = f"RSL_{name.upper()}_"
        self.name = name
        self.host = config(f"{prefix}HOST", default="localhost")
        self.port = config(f"{prefix}PORT", default="8888")
        self.user = config(f"{prefix}USER", default="admin")
        self.password = config(f"{prefix}PASS", default="")
        self.base_path = config(f"{prefix}BASE_PATH", default="/media/shares")
        self.base_url = f"https://{self.host}:{self.port}"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.client = httpx.Client(
            verify=ctx,
            auth=(self.user, self.password),
        )
        self._token: str | None = None

    def _get_token(self) -> str:
        resp = self.client.get(f"{self.base_url}/gui/token.html?t=0")
        resp.raise_for_status()
        match = re.search(r"id='token'[^>]*>([^<]+)<", resp.text)
        if not match:
            raise RuntimeError(f"Failed to extract token from: {resp.text}")
        return match.group(1)

    def api(self, params: str) -> dict:
        if self._token is None:
            self._token = self._get_token()
        resp = self.client.get(f"{self.base_url}/gui/?token={self._token}&{params}&t=0")
        resp.raise_for_status()
        return resp.json()

    def get_disconnected(self) -> list[dict]:
        result = self.api("action=getdisconnectedfolders")
        return result.get("value", [])

    def get_connected(self) -> list[dict]:
        result = self.api("action=getsyncfolders&discovery=1")
        # discovery=1 includes discovered-but-not-connected folders that lack
        # most keys (e.g. no 'path'). Filter to only fully connected folders.
        return [f for f in result.get("folders", []) if "path" in f]

    def add_folder(self, path: str) -> dict:
        encoded = quote(path, safe="")
        return self.api(f"action=addsyncfolder&path={encoded}")

    def connect_folder(self, folderid: str, path: str) -> dict:
        encoded = quote(path, safe="")
        return self.api(f"action=adddisconnectedfolder&folderid={folderid}&selectivesync=0&path={encoded}&force=true")

    def remove_folder(self, folderid: str) -> dict:
        return self.api(f"action=removefolder&folderid={folderid}")

    def set_folder_pref(self, folderid: str, key: str, value: str) -> dict:
        encoded_value = quote(value, safe="")
        return self.api(f"action=setfolderpref&folderid={folderid}&{key}={encoded_value}")

    def set_setting(self, key: str, value: str) -> dict:
        encoded_value = quote(value, safe="")
        return self.api(f"action=setsettings&{key}={encoded_value}")


def _check_result(result: dict) -> str | None:
    """Return error message if the API response indicates failure, else None."""
    if result.get("status") != 200:
        return str(result)
    value = result.get("value", {})
    if isinstance(value, dict) and value.get("error"):
        return value.get("message", f"error code {value['error']}")
    return None


def _normalize_value(value: str) -> str:
    """Convert true/false to 1/0 for the Resilio API."""
    match value.lower():
        case "true":
            return "1"
        case "false":
            return "0"
        case _:
            return value


def cmd_add(api: ResilioAPI, path: str):
    if not path.startswith("/"):
        path = f"{api.base_path}/{path}"

    connected = api.get_connected()
    if any(f["path"] == path for f in connected):
        print(f"Already synced: {path}")
        return 0

    print(f"Adding sync folder: {path}")
    result = api.add_folder(path)
    error = _check_result(result)
    if error:
        print(f"  Failed: {error}")
        return 1
    print("  OK")
    return 0


def cmd_list(names: tuple[str, ...]):
    for name in names:
        api = ResilioAPI(name)
        print(f"=== {name.upper()} ({api.host}:{api.port}) ===")

        disconnected = api.get_disconnected()
        if disconnected:
            print(f"Disconnected ({len(disconnected)}):")
            for f in sorted(disconnected, key=lambda x: x["name"]):
                print(f"  {f['name']}  (id: {f['folderid']})")
        else:
            print("No disconnected folders.")

        connected = api.get_connected()
        if connected:
            print(f"Connected ({len(connected)}):")
            for f in sorted(connected, key=lambda x: x["name"]):
                print(f"  {f['name']} -> {f['path']}")

        if name != names[-1]:
            print()


def cmd_connect(api: ResilioAPI, name: str, path: str | None = None):
    if path is None:
        path = f"{api.base_path}/{name}"

    disconnected = api.get_disconnected()
    match = [f for f in disconnected if f["name"] == name]
    if not match:
        print(f"Error: '{name}' not in disconnected list")
        available = [f["name"] for f in disconnected]
        if available:
            print(f"Available: {', '.join(sorted(available))}")
        return 1

    folderid = match[0]["folderid"]
    print(f"Connecting '{name}' (id: {folderid}) -> {path}")
    result = api.connect_folder(folderid, path)
    error = _check_result(result)
    if error:
        print(f"  Failed: {error}")
        return 1
    print("  OK")
    return 0


def cmd_connect_all(api: ResilioAPI):
    disconnected = api.get_disconnected()
    if not disconnected:
        print("No disconnected folders.")
        return

    print(f"Connecting {len(disconnected)} folders to {api.base_path}/...\n")
    errors = 0
    for f in sorted(disconnected, key=lambda x: x["name"]):
        result = cmd_connect(api, f["name"])
        if result:
            errors += 1

    if errors:
        print(f"\n{errors} folder(s) failed.")


def cmd_remove(api: ResilioAPI, name: str):
    connected = api.get_connected()
    match = [f for f in connected if f["name"] == name]
    if not match:
        print(f"Error: '{name}' not in connected folders")
        available = [f["name"] for f in connected]
        if available:
            print(f"Available: {', '.join(sorted(available))}")
        return 1

    folderid = match[0]["folderid"]
    print(f"Removing '{name}' (id: {folderid})")
    result = api.remove_folder(folderid)
    error = _check_result(result)
    if error:
        print(f"  Failed: {error}")
        return 1
    print("  OK")
    return 0


def cmd_set_pref(api: ResilioAPI, args: list[str]):
    # 2 args: key value (all folders)
    # 3 args: name key value (single folder)
    if len(args) == 2:
        key, value = args
        value = _normalize_value(value)
        connected = api.get_connected()
        if not connected:
            print("No connected folders.")
            return 0
        print(f"Setting {key}={value} on {len(connected)} folder(s)")
        errors = 0
        for f in sorted(connected, key=lambda x: x["name"]):
            result = api.set_folder_pref(f["folderid"], key, value)
            error = _check_result(result)
            if error:
                print(f"  {f['name']}: Failed: {error}")
                errors += 1
            else:
                print(f"  {f['name']}: OK")
        return 1 if errors else 0
    elif len(args) == 3:
        name, key, value = args
        value = _normalize_value(value)
        connected = api.get_connected()
        match = [f for f in connected if f["name"] == name]
        if not match:
            print(f"Error: '{name}' not in connected folders")
            available = [f["name"] for f in connected]
            if available:
                print(f"Available: {', '.join(sorted(available))}")
            return 1
        folderid = match[0]["folderid"]
        print(f"Setting {key}={value} on '{name}' (id: {folderid})")
        result = api.set_folder_pref(folderid, key, value)
        error = _check_result(result)
        if error:
            print(f"  Failed: {error}")
            return 1
        print("  OK")
        return 0
    else:
        print("Usage: rsl <server> set-pref [<name>] <key> <value>")
        return 1


def cmd_set_setting(api: ResilioAPI, args: list[str]):
    if len(args) != 2:
        print("Usage: rsl <server> set-setting <key> <value>")
        return 1
    key, value = args
    value = _normalize_value(value)
    print(f"Setting {key}={value} on {api.name}")
    result = api.set_setting(key, value)
    error = _check_result(result)
    if error:
        print(f"  Failed: {error}")
        return 1
    print("  OK")
    return 0


def main():
    args = sys.argv[1:]

    # Extract server name if first arg is a known server
    server: str | None = None
    if args and args[0] in SERVERS:
        server = args.pop(0)

    cmd = args[0] if args else "help"

    match cmd:
        case "list" | "ls":
            names = (server,) if server else SERVERS
            cmd_list(names)

        case "add":
            if server is None:
                print("Error: server required (e.g. rsl src add Books)")
                sys.exit(1)
            if len(args) < 2:
                print(f"Usage: rsl {server} add <name|path>")
                sys.exit(1)
            api = ResilioAPI(server)
            sys.exit(cmd_add(api, args[1]) or 0)

        case "connect":
            if server is None:
                print("Error: server required (e.g. rsl src connect <name>)")
                sys.exit(1)
            if len(args) < 2:
                print(f"Usage: rsl {server} connect <name> [path]")
                sys.exit(1)
            api = ResilioAPI(server)
            name = args[1]
            path = args[2] if len(args) > 2 else None
            sys.exit(cmd_connect(api, name, path) or 0)

        case "connect-all":
            if server is None:
                print("Error: server required (e.g. rsl src connect-all)")
                sys.exit(1)
            api = ResilioAPI(server)
            cmd_connect_all(api)

        case "remove" | "rm":
            if server is None:
                print("Error: server required (e.g. rsl src remove Books)")
                sys.exit(1)
            if len(args) < 2:
                print(f"Usage: rsl {server} remove <name>")
                sys.exit(1)
            api = ResilioAPI(server)
            sys.exit(cmd_remove(api, args[1]) or 0)

        case "set-pref":
            if server is None:
                print("Error: server required (e.g. rsl src set-pref selectivesync true)")
                sys.exit(1)
            if len(args) < 3:
                print(f"Usage: rsl {server} set-pref [<name>] <key> <value>")
                sys.exit(1)
            api = ResilioAPI(server)
            sys.exit(cmd_set_pref(api, args[1:]) or 0)

        case "set-setting":
            if server is None:
                print("Error: server required (e.g. rsl src set-setting worker_threads_count 1)")
                sys.exit(1)
            if len(args) < 3:
                print(f"Usage: rsl {server} set-setting <key> <value>")
                sys.exit(1)
            api = ResilioAPI(server)
            sys.exit(cmd_set_setting(api, args[1:]) or 0)

        case _:
            print(__doc__)


if __name__ == "__main__":
    main()
