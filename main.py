from __future__ import annotations

import hashlib
import os
import json
import queue

import sys
import threading
import webbrowser
import time
import tkinter as tk

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk
from typing import Any, Callable

import requests
from loguru import logger

try:
    import keyring

except Exception:
    keyring = None

try:
    import websocket

except Exception:
    websocket = None

APP_TITLE = "CATX Systems Torch RCON Tool v23.4.1.0"

def get_app_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        base = Path(local_app_data) / "CATX" / "TorchRemoteAdmin"

    else:
        base = Path.home() / ".catx" / "torch_remote_admin"

    base.mkdir(parents=True, exist_ok=True)
    return base

APP_DIR = get_app_dir()
SETTINGS_DIR = APP_DIR / "Settings"
LOG_DIR = APP_DIR / "Logs"

SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = SETTINGS_DIR / "torch_config.json"
PROGRAM_PROGRAM_LOG_FILE = LOG_DIR / "latest.log"
TORCH_PROGRAM_LOG_FILE = LOG_DIR / "torch_latest.log"

KEYRING_SERVICE = "CATX Systems Torch RCON Tool"
KEYRING_ACCOUNT = "default"

TOKEN_PLACEHOLDER = "••••••••••••••••"
STATUS_ENDPOINT = "/api/v1/server/status"
SERVER_SETTINGS_ENDPOINT = "/api/v1/server/settings"
PLAYERS_ENDPOINT = "/api/v1/players"
BANNED_PLAYERS_ENDPOINT = "/api/v1/players/banned"
PLUGINS_ENDPOINT = "/api/v1/plugins"
PLUGIN_DOWNLOADS_ENDPOINT = "/api/v1/plugins/downloads/"
SELECTED_WORLD_ENDPOINT = "/api/v1/worlds/selected"
SETTINGS_KEYS_ENDPOINT = "/api/v1/settings/"
COMMAND_ENDPOINT = "/api/v1/chat/command"

APP_VERSION = "23.4.1.0"
CONFIG_SCHEMA_VERSION = 7

LOGO_FILENAME = "logo.png"

def resource_path(relative_path: str) -> Path:

    if hasattr(sys, "_MEIPASS"):

        return Path(getattr(sys, "_MEIPASS")) / relative_path


    script_dir = Path(__file__).resolve().parent

    candidates = [

        script_dir / relative_path,

        APP_DIR / relative_path,

    ]


    for candidate in candidates:

        if candidate.exists():

            return candidate


    return script_dir / relative_path


LOGO_FILE = resource_path(LOGO_FILENAME)


KEYRING_SERVICE = "CATX Systems Torch RCON Tool"

KEYRING_ACCOUNT = "default"

TOKEN_PLACEHOLDER = "••••••••••••••••"
STATUS_ENDPOINT = "/api/v1/server/status"
SERVER_SETTINGS_ENDPOINT = "/api/v1/server/settings"
PLAYERS_ENDPOINT = "/api/v1/players"
BANNED_PLAYERS_ENDPOINT = "/api/v1/players/banned"
PLUGINS_ENDPOINT = "/api/v1/plugins"
PLUGIN_DOWNLOADS_ENDPOINT = "/api/v1/plugins/downloads/"
SELECTED_WORLD_ENDPOINT = "/api/v1/worlds/selected"
SETTINGS_KEYS_ENDPOINT = "/api/v1/settings/"
COMMAND_ENDPOINT = "/api/v1/chat/command"


LAST_RESPONSE_FILE = APP_DIR / "torch_remote.json"


APP_VERSION = "23.4.1.0"

CONFIG_SCHEMA_VERSION = 7


DEFAULT_COMMAND_ENDPOINT_CANDIDATES: list[str] = [

    COMMAND_ENDPOINT,

]


DEFAULT_PLAYERS_ENDPOINT_CANDIDATES = [


    PLAYERS_ENDPOINT,


    "/players",

    "/api/players",

    "/players/list",

    "/api/players/list",

]


def unique_keep_order(values: list[str]) -> list[str]:

    seen: set[str] = set()

    out: list[str] = []


    for value in values:

        value = str(value).strip()

        if value and value not in seen:

            seen.add(value)

            out.append(value)


    return out


@dataclass

class ClientConfig:

    app_version: str = APP_VERSION

    config_schema_version: int = CONFIG_SCHEMA_VERSION

    scheme: str = "http"

    host: str = "127.0.0.1"

    port: int = 60000

    token: str = ""

    token_hash: str = ""

    command_endpoint: str = COMMAND_ENDPOINT



    status_endpoint: str = STATUS_ENDPOINT

    players_endpoint: str = PLAYERS_ENDPOINT


    timeout_seconds: float = 10.0


    retry_404_attempts: int = 3

    retry_404_delay_seconds: float = 0.75
    custom_command_warning_acknowledged: bool = False
    server_chat_essentials_warning_acknowledged: bool = False


class TkLogSink:

    def __init__(self, q: queue.Queue[tuple[str, str]]) -> None:

        self.q = q


    def write(self, message: str) -> None:

        msg = message.rstrip()

        if not msg:

            return


        level = "INFO"

        if "| SUCCESS " in msg:

            level = "SUCCESS"

        elif "| WARNING " in msg:

            level = "WARNING"

        elif "| ERROR " in msg or "| CRITICAL" in msg:

            level = "ERROR"

        elif "| DEBUG " in msg:

            level = "DEBUG"


        self.q.put((level, msg))


class TorchRemoteClient:

    def __init__(self, cfg: ClientConfig) -> None:

        self.cfg = cfg

        self.session = requests.Session()


    @property

    def base_url(self) -> str:

        host = self.cfg.host.strip()

        scheme = self.cfg.scheme.strip().rstrip(":/") or "http"

        return f"{scheme}://{host}:{int(self.cfg.port)}"


    @property

    def ws_base_url(self) -> str:

        scheme = "wss" if self.cfg.scheme.lower().startswith("https") else "ws"

        return f"{scheme}://{self.cfg.host.strip()}:{int(self.cfg.port)}"


    def headers(self) -> dict[str, str]:

        headers = {

            "Accept": "application/json, text/plain, */*",

            "Content-Type": "application/json",

            "Accept-Encoding": "gzip, deflate",

            "User-Agent": "CATX-TorchRemoteTk/1.0",

        }


        token = self.cfg.token.strip()

        if token:

            headers["Authorization"] = f"Bearer {token}"

            headers["X-Api-Key"] = token

            headers["X-Security-Key"] = token


        return headers


    def url(self, endpoint: str) -> str:

        endpoint = endpoint.strip()

        if not endpoint:

            endpoint = "/"

        if not endpoint.startswith("/"):

            endpoint = "/" + endpoint

        return self.base_url + endpoint


    def ws_url(self, endpoint: str) -> str:

        endpoint = endpoint.strip()

        if not endpoint:

            endpoint = "/"

        if not endpoint.startswith("/"):

            endpoint = "/" + endpoint

        return self.ws_base_url + endpoint


    def request(

        self,

        method: str,

        endpoint: str,

        json_body: Any | None = None,

        params: dict[str, Any] | None = None,

        timeout_override: float | None = None,

    ) -> requests.Response:

        return self.session.request(

            method=method.upper(),

            url=self.url(endpoint),

            headers=self.headers(),

            json=json_body,

            params=params,

            timeout=self.cfg.timeout_seconds if timeout_override is None else timeout_override,

        )


    def request_with_policy(

        self,

        method: str,

        endpoint: str,

        json_body: Any | None = None,

        params: dict[str, Any] | None = None,

        timeout_override: float | None = None,

    ) -> requests.Response:

        attempts = max(1, int(self.cfg.retry_404_attempts))

        delay = max(0.0, float(self.cfg.retry_404_delay_seconds))


        last_response: requests.Response | None = None


        for attempt in range(1, attempts + 1):

            resp = self.request(method, endpoint, json_body=json_body, params=params, timeout_override=timeout_override)

            last_response = resp


            if resp.status_code != 404:

                return resp


            if attempt < attempts:

                logger.warning(

                    f"{method.upper()} {endpoint} returned 404; retry "

                    f"{attempt}/{attempts} after {delay:.2f}s"

                )

                if delay:

                    time.sleep(delay)


        assert last_response is not None

        return last_response


    def get(self, endpoint: str) -> requests.Response:

        return self.request_with_policy("GET", endpoint)


    def post(self, endpoint: str, body: Any | None = None) -> requests.Response:

        return self.request_with_policy("POST", endpoint, json_body=body)


    def try_command_payloads(self, endpoint: str, command: str) -> tuple[bool, str, int | None]:

        payloads: list[Any] = [

            {"Command": command, "Streamed": True, "StreamingDuration": "00:00:05"},

            {"Command": command, "Streamed": True, "StreamingDuration": "00:00:10"},

            {"Command": command, "Streamed": False},

            {"Command": command},

            {"command": command, "streamed": True, "streamingDuration": "00:00:05"},

            {"command": command},

        ]


        last_text = ""

        last_status: int | None = None


        for payload in payloads:

            try:

                resp = self.post(endpoint, payload)

                last_status = resp.status_code

                last_text = format_response(resp)


                if 200 <= resp.status_code < 300:

                    return True, last_text, resp.status_code


                if resp.status_code in (400, 415, 422):

                    continue


                if resp.status_code in (401, 403, 404, 405):

                    return False, last_text, resp.status_code


            except requests.RequestException as exc:

                last_text = str(exc)

                last_status = None

                return False, last_text, None


        return False, last_text, last_status


def setup_logging(q: queue.Queue[tuple[str, str]], debug: bool = False) -> None:

    logger.remove()


    logger.add(

        TkLogSink(q),

        level="DEBUG" if debug else "INFO",

        format="{time:HH:mm:ss} | {level:<8} | {message}",

    )


    logger.add(

        PROGRAM_PROGRAM_LOG_FILE,

        level="DEBUG",

        rotation="1 MB",

        retention=10,

        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",

        filter=lambda record: not record["extra"].get("torch", False),

    )


    logger.add(

        TORCH_PROGRAM_LOG_FILE,

        level="DEBUG",

        rotation="1 MB",

        retention=10,

        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",

        filter=lambda record: record["extra"].get("torch", False),

    )


def migrate_config(cfg: ClientConfig) -> ClientConfig:

    changed = False


    migrations = {

        "/api/server/status": STATUS_ENDPOINT,

        "/api/players": PLAYERS_ENDPOINT,

        "/api/chat/command": COMMAND_ENDPOINT,

        "/api/logs": "/api/v1/logs",

        "/api/logs/ws": "/api/live/logs",


        "/server/status": STATUS_ENDPOINT,

        "/players": PLAYERS_ENDPOINT,

        "/chat/command": COMMAND_ENDPOINT,

        "/logs": "/api/v1/logs",

        "/logs/ws": "/api/live/logs",

    }


    if cfg.status_endpoint in migrations:

        logger.warning(f"Migrating status endpoint {cfg.status_endpoint} -> {migrations[cfg.status_endpoint]}")

        cfg.status_endpoint = migrations[cfg.status_endpoint]

        changed = True


    if cfg.players_endpoint in migrations:

        logger.warning(f"Migrating players endpoint {cfg.players_endpoint} -> {migrations[cfg.players_endpoint]}")

        cfg.players_endpoint = migrations[cfg.players_endpoint]

        changed = True


    if cfg.command_endpoint in migrations:

        logger.warning(f"Migrating command endpoint {cfg.command_endpoint} -> {migrations[cfg.command_endpoint]}")

        cfg.command_endpoint = migrations[cfg.command_endpoint]

        changed = True


        changed = True


        changed = True


    if changed:

        save_config(cfg)


    return cfg


def store_token_securely(token: str) -> bool:

    token = token.strip()

    if not token:

        return False


    if keyring is None:

        logger.error("keyring is not installed. Install with: pip install keyring")

        return False


    try:

        keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, token)

        logger.success("SecurityKey stored in OS credential storage.")

        return True

    except Exception as exc:

        logger.error(f"Could not store SecurityKey in OS credential storage: {exc}")

        return False


def load_token_securely() -> str:

    if keyring is None:

        logger.warning("keyring is not installed; saved SecurityKey cannot be loaded securely.")

        return ""


    try:

        token = keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)

        return (token or "").strip()

    except Exception as exc:

        logger.warning(f"Could not load SecurityKey from OS credential storage: {exc}")

        return ""


def delete_token_securely() -> bool:

    if keyring is None:

        logger.warning("keyring is not installed; no OS-stored SecurityKey to delete.")

        return False


    try:

        keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)

        logger.success("Deleted SecurityKey from OS credential storage.")

        return True

    except Exception as exc:

        logger.warning(f"Could not delete SecurityKey from OS credential storage: {exc}")

        return False


def load_config() -> ClientConfig:

    if not CONFIG_FILE.exists():

        return ClientConfig()


    try:

        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

        if not isinstance(data, dict):

            return ClientConfig()


        base = asdict(ClientConfig())

        base.update(data)


        legacy_plaintext_token = str(base.get("token", "")).strip()

        base["token"] = ""

        base["token_hash"] = str(base.get("token_hash", ""))


        valid_config_keys = {field.name for field in fields(ClientConfig)}
        ignored_keys = sorted(set(base) - valid_config_keys)
        if ignored_keys:
            logger.warning(f"Ignoring legacy/unknown config keys: {', '.join(ignored_keys)}")
        base = {key: value for key, value in base.items() if key in valid_config_keys}

        cfg = migrate_config(ClientConfig(**base))


        if legacy_plaintext_token:

            logger.warning("Migrating legacy plaintext SecurityKey from config into OS credential storage.")

            store_token_securely(legacy_plaintext_token)

            cfg.token = legacy_plaintext_token

            cfg.token_hash = hash_token(legacy_plaintext_token)

            save_config(cfg)

            return cfg


        secure_token = load_token_securely()

        if secure_token:

            cfg.token = secure_token

            cfg.token_hash = hash_token(secure_token)


        return cfg


        base["app_version"] = str(base.get("app_version", APP_VERSION))

        base["config_schema_version"] = int(base.get("config_schema_version", 1))


        if base["config_schema_version"] < CONFIG_SCHEMA_VERSION:

            logger.warning(

                f"Migrating config schema {base['config_schema_version']} -> {CONFIG_SCHEMA_VERSION}"

            )

            base["config_schema_version"] = CONFIG_SCHEMA_VERSION


        base["app_version"] = APP_VERSION


        base["port"] = int(base.get("port", 60000))

        base["timeout_seconds"] = float(base.get("timeout_seconds", 10.0))


        base["retry_404_attempts"] = int(base.get("retry_404_attempts", 3))

        base["retry_404_delay_seconds"] = float(base.get("retry_404_delay_seconds", 0.75))
        base["custom_command_warning_acknowledged"] = bool(base.get("custom_command_warning_acknowledged", False))
        base["server_chat_essentials_warning_acknowledged"] = bool(base.get("server_chat_essentials_warning_acknowledged", False))


        raise RuntimeError("Internal config load flow error.")


    except Exception as exc:

        logger.warning(f"Could not load config, using defaults: {exc}")

        return ClientConfig()


def save_config(cfg: ClientConfig) -> None:

    data = asdict(cfg)

    data["app_version"] = APP_VERSION

    data["config_schema_version"] = CONFIG_SCHEMA_VERSION


    token = str(data.get("token", "")).strip()

    previous_hash = str(data.get("token_hash", "")).strip()


    data["token_hash"] = hash_token(token) if token else previous_hash

    data["token"] = ""


    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def pretty_json(value: Any) -> str:

    return json.dumps(value, indent=2, ensure_ascii=False)


def torch_log(level: str, message: str) -> None:

    logger.bind(torch=True).log(level, message)


def torch_info(message: str) -> None:

    torch_log("INFO", message)


def torch_success(message: str) -> None:

    torch_log("SUCCESS", message)


def torch_warning(message: str) -> None:

    torch_log("WARNING", message)


def torch_error(message: str) -> None:

    torch_log("ERROR", message)


def compact_json(value: Any, max_len: int = 220) -> str:

    try:

        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    except Exception:

        text = str(value)


    if len(text) > max_len:

        return text[:max_len] + "..."

    return text


def semantic_level_for_status(status_code: int) -> str:

    if 200 <= status_code < 300:

        return "SUCCESS"

    if status_code in (401, 403):

        return "ERROR"

    if status_code == 404:

        return "WARNING"

    if status_code >= 500:

        return "ERROR"

    if status_code >= 300:

        return "WARNING"

    return "INFO"


def multiline_json_summary(endpoint: str, value: Any) -> list[str]:

    endpoint = endpoint.rstrip("/")


    if endpoint.endswith("/server/status") and isinstance(value, dict):

        return [

            f"simSpeed: {value.get('simSpeed', '?')}",

            f"players:  {value.get('memberCount', '?')}",

            f"uptime:   {value.get('uptime', '?')}",

            f"status:   {value.get('status', '?')}",

        ]


    if endpoint.endswith("/server/settings") and isinstance(value, dict):

        listen = value.get("listenEndPoint") or {}

        ip = listen.get("ip", "?") if isinstance(listen, dict) else "?"

        port = listen.get("port", "?") if isinstance(listen, dict) else "?"

        return [

            f"name:        {value.get('serverName', '?')}",

            f"map:         {value.get('mapName', '') or '(blank)'}",

            f"players max: {value.get('memberLimit', '?')}",

            f"listen:      {ip}:{port}",

        ]


    if endpoint.endswith("/players") and isinstance(value, list):

        if not value:

            return ["online players: 0"]

        rows = [f"online players: {len(value)}"]

        for item in value[:12]:

            if isinstance(item, dict):

                name = item.get("displayName") or item.get("name") or item.get("steamName") or item.get("id") or "?"

                rows.append(f"- {name}")

            else:

                rows.append(f"- {item}")

        if len(value) > 12:

            rows.append(f"... +{len(value) - 12} more")

        return rows


    if endpoint.endswith("/players/banned") and isinstance(value, list):

        return [f"banned players: {len(value)}"]


    if endpoint.endswith("/plugins") and isinstance(value, list):

        rows = [f"plugins: {len(value)}"]

        for item in value[:14]:

            if isinstance(item, dict):

                name = item.get("name", "?")

                version = item.get("version") or item.get("latestVersion") or ""

                suffix = f" ({version})" if version else ""

                rows.append(f"- {name}{suffix}")

            else:

                rows.append(f"- {item}")

        if len(value) > 14:

            rows.append(f"... +{len(value) - 14} more")

        return rows


    if endpoint.endswith("/plugins/downloads") and isinstance(value, list):

        rows = [f"available plugin downloads: {len(value)}"]

        for item in value[:10]:

            if isinstance(item, dict):

                name = item.get("name", "?")

                version = item.get("latestVersion") or ""

                author = item.get("author") or ""

                parts = [name]

                if version:

                    parts.append(version)

                if author:

                    parts.append(f"by {author}")

                rows.append("- " + " | ".join(parts))

        if len(value) > 10:

            rows.append(f"... +{len(value) - 10} more")

        return rows


    if endpoint.endswith("/chat/message"):

        if isinstance(value, dict):

            return [

                "chat message accepted",

                compact_json(value, 500),

            ]

        if isinstance(value, list):

            return [f"chat message response items: {len(value)}", compact_json(value, 500)]

        if value in (None, "", True):

            return ["chat message accepted"]

        return [f"chat message response: {value}"]


    if endpoint.endswith("/chat/command") and isinstance(value, list):

        if not value:

            return ["command response: no output"]


        rows = ["command response:"]

        for item in value:

            if isinstance(item, dict):

                author = item.get("author") or "Server"

                message = item.get("message") or item.get("text") or item.get("content") or ""

                if message:

                    rows.append(f"{author}: {message}")

                else:

                    rows.append(compact_json(item, 500))

            else:

                rows.append(str(item))

        return rows


    if endpoint.endswith("/worlds/selected"):

        return [f"selected world: {value}"]


    if endpoint.endswith("/settings") and isinstance(value, list):

        rows = [f"settings keys: {len(value)}"]

        for item in value[:12]:

            rows.append(f"- {item}")

        if len(value) > 12:

            rows.append(f"... +{len(value) - 12} more")

        return rows


    if isinstance(value, dict):

        return [compact_json(value, 500)]


    if isinstance(value, list):

        return [f"items: {len(value)}", compact_json(value, 500)]


    return [str(value)]


def response_summary(resp: requests.Response, endpoint: str = "") -> tuple[str, str]:

    content_type = resp.headers.get("Content-Type", "")

    header = f"{resp.request.method if resp.request else 'HTTP'} {endpoint} -> HTTP {resp.status_code} {resp.reason}"


    try:

        if "json" in content_type.lower():

            payload = resp.json()

            body = "\n".join(f"  {line}" for line in multiline_json_summary(endpoint, payload))

            return semantic_level_for_status(resp.status_code), f"{header}\n{body}"

    except Exception:

        pass


    text = (resp.text or "").strip().replace("\n", " ")

    if len(text) > 700:

        text = text[:700] + "..."

    return semantic_level_for_status(resp.status_code), f"{header}\n  {text}"


def log_response(resp: requests.Response, endpoint: str = "") -> None:

    level, message = response_summary(resp, endpoint)

    torch_log(level, message)


def format_response(resp: requests.Response) -> str:

    content_type = resp.headers.get("Content-Type", "")

    head = f"HTTP {resp.status_code} {resp.reason}\nContent-Type: {content_type}\n"


    try:

        if "json" in content_type.lower():

            return head + pretty_json(resp.json())

    except Exception:

        pass


    text = resp.text or ""

    if len(text) > 12000:

        text = text[:12000] + "\n... truncated ..."

    return head + text


def hash_token(token: str) -> str:

    token = token.strip()

    if not token:

        return ""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def short_hash(value: str) -> str:

    value = value.strip()

    if not value:

        return "none"

    return value[:12] + "..."


def parse_json_maybe(raw: str) -> Any:

    raw = raw.strip()

    if not raw:

        return None

    return json.loads(raw)


def quote_command_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{escaped}\""


def command_timeout_seconds(streamed: bool, streaming_seconds: int, base_timeout: float) -> float:

    if not streamed:

        return max(float(base_timeout), 10.0)


    return max(float(base_timeout), float(streaming_seconds) + 10.0)


class App:

    def __init__(self, root: tk.Tk) -> None:

        self.root = root

        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        setup_logging(self.log_queue)


        self.cfg = load_config()

        self.client = TorchRemoteClient(self.cfg)


        self.worker: threading.Thread | None = None


        self.command_endpoint_var = tk.StringVar()

        self.status_endpoint_var = tk.StringVar()

        self.players_endpoint_var = tk.StringVar()


        self.build_styles()

        self.apply_window_icon()

        self.build_ui()

        self.load_config_to_ui()


        self.root.after(100, self.drain_logs)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)


        logger.info("Ready.")

        logger.info("CATX Systems Torch RCON Tool v23.4.1.0")


    def apply_window_icon(self) -> None:

        try:

            if LOGO_FILE.exists():

                self._app_icon = tk.PhotoImage(file=str(LOGO_FILE))

                self.root.iconphoto(True, self._app_icon)

                return


            logger.warning(f"Logo not found; running with default Tk icon: {LOGO_FILE}")

        except Exception as exc:

            logger.warning(f"Could not apply app logo/icon:\n  {exc}")


    def build_styles(self) -> None:

        self.root.title(APP_TITLE)

        self.root.geometry("1440x980")

        self.root.minsize(1366, 900)

        self.root.configure(bg="#090d13")


        style = ttk.Style()

        try:

            style.theme_use("clam")

        except tk.TclError:

            pass


        self.colors = {

            "bg": "#090d13",

            "panel": "#101822",

            "panel2": "#152231",

            "panel3": "#0d141d",

            "fg": "#d9e7f3",

            "muted": "#8fa2b3",

            "accent": "#72e0ff",

            "accent2": "#ff9f43",

            "border": "#263648",

            "success": "#a3ffb3",

            "warning": "#ffd36a",

            "error": "#ff7b91",

            "debug": "#9aa8b5",

        }


        style.configure(".", background=self.colors["bg"], foreground=self.colors["fg"], fieldbackground=self.colors["panel2"], font=("Segoe UI", 10))

        style.configure("TFrame", background=self.colors["bg"])

        style.configure("Panel.TFrame", background=self.colors["panel"])

        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["fg"])

        style.configure("Panel.TLabel", background=self.colors["panel"], foreground=self.colors["fg"])

        style.configure("Muted.TLabel", background=self.colors["bg"], foreground=self.colors["muted"])
        style.configure("Link.TLabel", background=self.colors["bg"], foreground=self.colors["accent"])

        style.configure("Title.TLabel", background=self.colors["panel"], foreground=self.colors["fg"], font=("Segoe UI Semibold", 18))

        style.configure("Subtitle.TLabel", background=self.colors["panel"], foreground=self.colors["muted"], font=("Segoe UI", 10))

        style.configure("Section.TLabelframe", background=self.colors["bg"], bordercolor=self.colors["border"], relief="solid")

        style.configure("Section.TLabelframe.Label", background=self.colors["bg"], foreground=self.colors["accent"], font=("Segoe UI Semibold", 10))

        style.configure("TEntry", fieldbackground=self.colors["panel2"], foreground=self.colors["fg"], insertcolor=self.colors["fg"], bordercolor=self.colors["border"])

        style.configure(

            "TCombobox",

            fieldbackground=self.colors["panel2"],

            background=self.colors["panel2"],

            foreground=self.colors["fg"],

            arrowcolor=self.colors["fg"],

            bordercolor=self.colors["border"],

            lightcolor=self.colors["border"],

            darkcolor=self.colors["border"],

        )

        style.map(

            "TCombobox",

            fieldbackground=[("readonly", self.colors["panel2"]), ("focus", "#1a2a3d")],

            background=[("readonly", self.colors["panel2"]), ("active", "#203044")],

            foreground=[("readonly", self.colors["fg"])],

            arrowcolor=[("active", self.colors["accent"]), ("readonly", self.colors["fg"])],

        )


        self.root.option_add("*TCombobox*Listbox.background", self.colors["panel2"])

        self.root.option_add("*TCombobox*Listbox.foreground", self.colors["fg"])

        self.root.option_add("*TCombobox*Listbox.selectBackground", "#0d4d63")

        self.root.option_add("*TCombobox*Listbox.selectForeground", "#e9fbff")

        self.root.option_add("*TCombobox*Listbox.font", "Segoe UI 10")


        style.configure(

            "TNotebook",

            background=self.colors["bg"],

            borderwidth=0,

            tabmargins=(2, 4, 2, 0),

        )

        style.configure(

            "TNotebook.Tab",

            background=self.colors["panel2"],

            foreground=self.colors["muted"],

            bordercolor=self.colors["border"],

            lightcolor=self.colors["border"],

            darkcolor=self.colors["border"],

            padding=(14, 8),

            font=("Segoe UI Semibold", 10),

        )

        style.map(

            "TNotebook.Tab",

            background=[("selected", "#0d4d63"), ("active", "#203044")],

            foreground=[("selected", "#e9fbff"), ("active", self.colors["fg"])],

        )

        style.configure("TButton", background=self.colors["panel2"], foreground=self.colors["fg"], bordercolor=self.colors["border"], padding=(10, 7))

        style.map("TButton", background=[("active", "#203044"), ("pressed", "#0e141d")])

        style.configure("Accent.TButton", background="#0d4d63", foreground="#e9fbff", bordercolor="#16708c", padding=(12, 8), font=("Segoe UI Semibold", 10))

        style.map("Accent.TButton", background=[("active", "#12627d"), ("pressed", "#093947")])

        style.configure("Warn.TButton", background="#4d3712", foreground="#fff4dc", bordercolor="#75531a", padding=(10, 7))

        style.configure("Danger.TButton", background="#50232a", foreground="#fff0f2", bordercolor="#6a3038", padding=(10, 7))

        style.configure(

            "TCheckbutton",

            background=self.colors["bg"],

            foreground=self.colors["fg"],

            focuscolor=self.colors["bg"],

            bordercolor=self.colors["border"],

            lightcolor=self.colors["bg"],

            darkcolor=self.colors["bg"],

        )

        style.map(

            "TCheckbutton",

            background=[

                ("active", self.colors["bg"]),

                ("pressed", self.colors["bg"]),

                ("selected", self.colors["bg"]),

                ("focus", self.colors["bg"]),

                ("disabled", self.colors["bg"]),

            ],

            foreground=[

                ("active", self.colors["fg"]),

                ("pressed", self.colors["fg"]),

                ("selected", self.colors["fg"]),

                ("focus", self.colors["fg"]),

                ("disabled", self.colors["muted"]),

            ],

            indicatorcolor=[

                ("selected", self.colors["accent"]),

                ("active", self.colors["panel2"]),

                ("!selected", self.colors["panel2"]),

            ],

        )


    def build_ui(self) -> None:

        outer = ttk.Frame(self.root, padding=14)

        outer.pack(fill="both", expand=True)


        hero = ttk.Frame(outer, style="Panel.TFrame", padding=(18, 14))

        hero.pack(fill="x")


        ttk.Label(hero, text="CATX Torch RCON Tool", style="Title.TLabel").grid(row=0, column=0, sticky="w")

        ttk.Label(

            hero,

            text="HTTP/Bearer-token admin client for Torch Remote. Profiles, route probing, command sender, console/log view.",

            style="Subtitle.TLabel",

        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        hero.columnconfigure(0, weight=1)


        body = ttk.Frame(outer)

        body.pack(fill="both", expand=True, pady=(12, 0))


        left = ttk.Frame(body)

        left.pack(side="left", fill="y", padx=(0, 12))


        right = ttk.Frame(body)

        right.pack(side="left", fill="both", expand=True)


        self.build_connection_panel(left)

        self.build_command_panel(left)

        self.build_quick_buttons(left)

        self.build_console_panel(right)


    def build_connection_panel(self, parent: ttk.Frame) -> None:

        frame = ttk.LabelFrame(parent, text="Connection", style="Section.TLabelframe", padding=12)

        frame.pack(fill="x", pady=(0, 10))


        self.scheme_var = tk.StringVar()

        self.host_var = tk.StringVar()

        self.port_var = tk.StringVar()

        self.token_var = tk.StringVar()

        self.token_hash_var = tk.StringVar(value="none")

        self.timeout_var = tk.StringVar()


        ttk.Label(frame, text="Scheme").grid(row=0, column=0, sticky="w")

        scheme = ttk.Combobox(frame, textvariable=self.scheme_var, values=["http", "https"], state="readonly", width=8)

        scheme.grid(row=1, column=0, sticky="w", pady=(3, 8))


        ttk.Label(frame, text="Host/IP").grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Entry(frame, textvariable=self.host_var, width=23).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(3, 8))


        ttk.Label(frame, text="Port").grid(row=0, column=2, sticky="w", padx=(8, 0))

        ttk.Entry(frame, textvariable=self.port_var, width=8).grid(row=1, column=2, sticky="w", padx=(8, 0), pady=(3, 8))


        ttk.Label(frame, text="Bearer token / SecurityKey").grid(row=2, column=0, columnspan=3, sticky="w")

        ttk.Entry(frame, textvariable=self.token_var, width=48, show="•").grid(row=3, column=0, columnspan=3, sticky="ew", pady=(3, 4))


        ttk.Button(frame, text="Save Config", command=self.save_from_ui).grid(row=4, column=0, sticky="ew", pady=(10, 0))

        ttk.Button(frame, text="Forget Key", command=self.forget_saved_key).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(10, 0))

        ttk.Button(frame, text="Test", command=self.test_connection, style="Accent.TButton").grid(row=4, column=2, sticky="ew", padx=(8, 0), pady=(10, 0))


        frame.columnconfigure(1, weight=1)


    def build_command_panel(self, parent: ttk.Frame) -> None:

        frame = ttk.LabelFrame(parent, text="Command", style="Section.TLabelframe", padding=12)

        frame.pack(fill="x", pady=(0, 10))


        self.command_var = tk.StringVar(value="uptime")

        self.stream_command_var = tk.BooleanVar(value=True)

        self.command_stream_duration_var = tk.StringVar(value="15")


        ttk.Label(

            frame,

            text="Send Torch Remote commands over HTTP.",

            style="Muted.TLabel",

            wraplength=360,

        ).pack(fill="x", pady=(0, 8))


        ttk.Entry(frame, textvariable=self.command_var, width=48).pack(fill="x")


        opts = ttk.Frame(frame)

        opts.pack(fill="x", pady=(8, 0))

        ttk.Checkbutton(opts, text="Stream HTTP response", variable=self.stream_command_var).pack(side="left")

        ttk.Label(opts, text="seconds").pack(side="left", padx=(10, 4))

        ttk.Entry(opts, textvariable=self.command_stream_duration_var, width=6).pack(side="left")


        ttk.Button(frame, text="Send Command", command=self.send_command, style="Accent.TButton").pack(fill="x", pady=(8, 0))


    def build_quick_buttons(self, parent: ttk.Frame) -> None:

        frame = ttk.LabelFrame(parent, text="REST Quick Actions", style="Section.TLabelframe", padding=12)

        frame.pack(fill="x", pady=(0, 10))


        buttons = [

            ("Status", "GET", STATUS_ENDPOINT),

            ("Server Settings", "GET", SERVER_SETTINGS_ENDPOINT),

            ("Players", "GET", PLAYERS_ENDPOINT),

            ("Banned Players", "GET", BANNED_PLAYERS_ENDPOINT),

            ("Plugins", "GET", PLUGINS_ENDPOINT),

            ("Plugin Downloads", "GET", PLUGIN_DOWNLOADS_ENDPOINT),

            ("Selected World", "GET", SELECTED_WORLD_ENDPOINT),

            ("Settings Keys", "GET", SETTINGS_KEYS_ENDPOINT),

        ]


        for i, (label, method, endpoint) in enumerate(buttons):

            ttk.Button(

                frame,

                text=label,

                command=lambda m=method, e=endpoint: self.send_rest_shortcut(m, e),

            ).grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)


        frame.columnconfigure(0, weight=1)

        frame.columnconfigure(1, weight=1)


        ttk.Button(frame, text="Probe Documented REST Routes", command=self.probe_routes, style="Accent.TButton").grid(

            row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=(10, 4)

        )


    def build_console_panel(self, parent: ttk.Frame) -> None:

        notebook = ttk.Notebook(parent)

        notebook.pack(fill="both", expand=True)


        console_tab = ttk.Frame(notebook)

        settings_tab = ttk.Frame(notebook)

        about_tab = ttk.Frame(notebook)


        notebook.add(console_tab, text="Console")

        notebook.add(settings_tab, text="Settings")

        notebook.add(about_tab, text="About")


        self.build_console_tab(console_tab)

        self.build_settings_tab(settings_tab)

        self.build_about_tab(about_tab)


    def open_path(self, path: Path) -> None:

        try:

            path.mkdir(parents=True, exist_ok=True)

            os.startfile(str(path))

        except Exception as exc:

            logger.error(f"Could not open path:\n  {path}\n  {exc}")


    def open_file_location(self, file_path: Path) -> None:

        try:

            file_path.parent.mkdir(parents=True, exist_ok=True)

            if file_path.exists():

                os.startfile(str(file_path.parent))

            else:

                os.startfile(str(file_path.parent))

        except Exception as exc:

            logger.error(f"Could not open file location:\n  {file_path}\n  {exc}")


    def build_settings_tab(self, parent: ttk.Frame) -> None:

        frame = ttk.Frame(parent, padding=18)

        frame.pack(fill="both", expand=True)


        ttk.Label(

            frame,

            text="Settings",

            font=("Segoe UI Semibold", 16),

        ).pack(anchor="w", pady=(0, 10))


        info = (

            "Settings, logs, and runtime files are stored here:\n\n"

            f"{APP_DIR}\n\n"

        )


        info_box = tk.Text(

            frame,

            wrap="word",

            bg="#06090d",

            fg=self.colors["fg"],

            insertbackground=self.colors["fg"],

            relief="flat",

            borderwidth=0,

            padx=12,

            pady=10,

            font=("Cascadia Mono", 10),

            height=8,

        )

        info_box.pack(fill="x", pady=(0, 12))

        info_box.insert("1.0", info)

        info_box.configure(state="disabled")


        buttons = ttk.Frame(frame)

        buttons.pack(fill="x")


        ttk.Button(

            buttons,

            text="Open Settings Folder",

            command=lambda: self.open_path(APP_DIR),

            style="Accent.TButton",

        ).grid(row=0, column=0, sticky="ew", padx=4, pady=4)


        ttk.Button(

            buttons,

            text="Forget Saved SecurityKey",

            command=self.forget_saved_key,

            style="Warn.TButton",

        ).grid(row=0, column=1, sticky="ew", padx=4, pady=4)


        buttons.columnconfigure(0, weight=1)

        buttons.columnconfigure(1, weight=1)


    def build_about_tab(self, parent: ttk.Frame) -> None:

        frame = ttk.Frame(parent, padding=18)

        frame.pack(fill="both", expand=True)


        header = ttk.Frame(frame)

        header.pack(fill="x", pady=(0, 12))


        if LOGO_FILE.exists():

            try:

                self._about_logo = tk.PhotoImage(file=str(LOGO_FILE))

                max_size = 96

                w = max(1, self._about_logo.width())

                h = max(1, self._about_logo.height())

                factor = max(1, int(max(w / max_size, h / max_size)))

                if factor > 1:

                    self._about_logo = self._about_logo.subsample(factor, factor)

                ttk.Label(header, image=self._about_logo).pack(side="left", padx=(0, 14))

            except Exception as exc:

                logger.warning(f"Could not load About logo:\n  {exc}")


        title_block = ttk.Frame(header)

        title_block.pack(side="left", fill="x", expand=True)


        ttk.Label(

            title_block,

            text=f"CATX Systems Torch RCON Tool v{APP_VERSION}",

            font=("Segoe UI Semibold", 16),

        ).pack(anchor="w")


        ttk.Label(

            title_block,

            text="Aurora Tejeda · CATX Systems LLC",

            style="Muted.TLabel",

        ).pack(anchor="w", pady=(4, 0))


        about_text = (

            "Purpose:\n"

            "  Local Windows admin client for Torch Remote-enabled Space Engineers servers.\n"

            "  Uses documented REST endpoints and streamed HTTP command responses.\n\n"

            "Storage:\n"

            f"  App directory: {APP_DIR}\n"

            "  Config file: Settings/torch_remote_client_config.json\n"

            "  Program log: Logs/latest.log, retaining 10 rotated logs\n"

            "  Torch/API log: Logs/torch_latest.log, retaining 10 rotated logs\n"

            "  SecurityKey storage: OS credential storage via keyring.\n\n"

            "Attributions / Dependencies:\n"

            "  Python — Python Software Foundation License.\n"

            "  Tkinter / Tcl/Tk — bundled with Python builds where available; Tcl/Tk uses BSD-style licensing.\n"

            "  Requests — Apache License 2.0.\n"

            "  Loguru — MIT License.\n"

            "  Keyring — MIT License.\n"

            "  Pillow — Historical PIL Software License / HPND-style license, used by the build script for PNG → ICO conversion.\n"

            "  PyInstaller — GPLv2-or-later with bootloader exception, when used for packaging.\n\n"

            "Third-party context:\n"

            "  Torch Remote and Space Engineers are separate third-party projects/products.\n"

            "  This client is not affiliated with Keen Software House or the Torch project.\n"

        )


        text = tk.Text(

            frame,

            wrap="word",

            bg="#06090d",

            fg=self.colors["fg"],

            insertbackground=self.colors["fg"],

            relief="flat",

            borderwidth=0,

            padx=12,

            pady=10,

            font=("Cascadia Mono", 10),

        )

        text.pack(fill="both", expand=True)

        text.insert("1.0", about_text)

        text.configure(state="disabled")


    def build_console_tab(self, parent: ttk.Frame) -> None:

        controls = ttk.Frame(parent)

        controls.pack(fill="x", pady=(0, 8))


        self.ws_logs_var = tk.BooleanVar()
        ttk.Button(controls, text="Clear", command=self.clear_console).pack(side="right")


        self.console = tk.Text(

            parent,

            wrap="word",

            bg="#06090d",

            fg=self.colors["fg"],

            insertbackground=self.colors["fg"],

            relief="flat",

            borderwidth=0,

            padx=12,

            pady=10,

            font=("Cascadia Mono", 10),

        )

        self.console.pack(fill="both", expand=True)

        chat_bar = ttk.Frame(parent)
        chat_bar.pack(fill="x", pady=(8, 0))

        self.server_chat_var = tk.StringVar()

        ttk.Label(chat_bar, text="Server Chat").pack(side="left", padx=(0, 8))

        chat_entry = ttk.Entry(chat_bar, textvariable=self.server_chat_var)
        chat_entry.pack(side="left", fill="x", expand=True)
        chat_entry.bind("<Return>", lambda _event: self.send_server_chat())

        ttk.Button(
            chat_bar,
            text="Send",
            command=self.send_server_chat,
            style="Accent.TButton",
        ).pack(side="left", padx=(8, 0))


        self.console.tag_configure("INFO", foreground=self.colors["fg"])

        self.console.tag_configure("SUCCESS", foreground=self.colors["success"])

        self.console.tag_configure("WARNING", foreground=self.colors["warning"])

        self.console.tag_configure("ERROR", foreground=self.colors["error"])

        self.console.tag_configure("DEBUG", foreground=self.colors["debug"])

        self.console.configure(state="disabled")


    def load_config_to_ui(self) -> None:

        self.scheme_var.set(self.cfg.scheme)

        self.host_var.set(self.cfg.host)

        self.port_var.set(str(self.cfg.port))

        self.token_var.set(TOKEN_PLACEHOLDER if self.cfg.token else "")

        self.token_hash_var.set(short_hash(self.cfg.token_hash))

        self.timeout_var.set(str(self.cfg.timeout_seconds))

        self.command_endpoint_var.set(self.cfg.command_endpoint)


        self.status_endpoint_var.set(self.cfg.status_endpoint)

        self.players_endpoint_var.set(self.cfg.players_endpoint)


    def config_from_ui(self) -> ClientConfig:

        typed_token = self.token_var.get().strip()

        if typed_token == TOKEN_PLACEHOLDER:

            typed_token = ""


        active_token = typed_token or self.cfg.token or load_token_securely()


        return ClientConfig(

            scheme=self.scheme_var.get().strip() or "http",

            host=self.host_var.get().strip() or "127.0.0.1",

            port=int(self.port_var.get().strip() or "60000"),

            token=active_token,

            token_hash=hash_token(active_token) or self.cfg.token_hash,

            command_endpoint=self.command_endpoint_var.get().strip() or COMMAND_ENDPOINT,



            status_endpoint=self.status_endpoint_var.get().strip() or STATUS_ENDPOINT,

            players_endpoint=self.players_endpoint_var.get().strip() or PLAYERS_ENDPOINT,


            timeout_seconds=float(self.timeout_var.get().strip() or str(self.cfg.timeout_seconds or 10)),


            retry_404_attempts=int(getattr(self.cfg, "retry_404_attempts", 3)),

            retry_404_delay_seconds=float(getattr(self.cfg, "retry_404_delay_seconds", 0.75)),

        )


    def forget_saved_key(self) -> None:

        if not messagebox.askyesno("Forget SecurityKey", "Delete the saved SecurityKey from OS credential storage?"):

            return


        delete_token_securely()

        self.cfg.token = ""

        self.cfg.token_hash = ""

        self.token_var.set("")

        self.token_hash_var.set("none")

        save_config(self.cfg)

        logger.success("SecurityKey forgotten.")


    def save_from_ui(self) -> None:

        try:

            self.cfg = self.config_from_ui()


            if self.cfg.token:

                if store_token_securely(self.cfg.token):

                    self.cfg.token_hash = hash_token(self.cfg.token)

                else:

                    logger.warning("SecurityKey is active for this session only because secure storage failed.")


            self.client = TorchRemoteClient(self.cfg)

            save_config(self.cfg)

            self.token_hash_var.set(short_hash(self.cfg.token_hash))


            if self.cfg.token:

                self.token_var.set(TOKEN_PLACEHOLDER)

                logger.info("SecurityKey is loaded for this session.")

            logger.success(f"Saved config: {CONFIG_FILE}")

        except Exception as exc:

            messagebox.showerror("Invalid Config", str(exc))


    def refresh_client(self) -> bool:

        try:

            self.cfg = self.config_from_ui()

            self.client = TorchRemoteClient(self.cfg)

            self.token_hash_var.set(short_hash(self.cfg.token_hash))

            return True

        except Exception as exc:

            messagebox.showerror("Invalid Config", str(exc))

            return False


    def run_worker(self, fn: Callable[[], None]) -> None:

        if self.worker and self.worker.is_alive():

            messagebox.showwarning("Busy", "A request is already running.")

            return


        self.worker = threading.Thread(target=fn, daemon=True)

        self.worker.start()


    def append_console(self, level: str, text: str) -> None:

        self.console.configure(state="normal")

        self.console.insert("end", text + "\n", level)

        self.console.see("end")

        self.console.configure(state="disabled")


    def drain_logs(self) -> None:

        while True:

            try:

                level, msg = self.log_queue.get_nowait()

            except queue.Empty:

                break

            self.append_console(level, msg)

        self.root.after(100, self.drain_logs)


    def clear_console(self) -> None:

        self.console.configure(state="normal")

        self.console.delete("1.0", "end")

        self.console.configure(state="disabled")


    def maybe_show_custom_command_warning(self) -> bool:
        if self.cfg.custom_command_warning_acknowledged:
            return True

        dialog = tk.Toplevel(self.root)
        dialog.title("Custom Command Warning")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=self.colors["bg"])

        result = {"continue": False}
        dont_show_var = tk.BooleanVar(value=False)

        container = ttk.Frame(dialog, padding=18)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Custom commands can change or break server state.",
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            container,
            text=(
                "Only send commands you understand. Some Torch/plugin commands can stop the server, "
                "delete data, change ownership, clean grids, or otherwise affect players."
            ),
            style="Muted.TLabel",
            wraplength=440,
        ).pack(anchor="w", pady=(0, 12))

        ttk.Checkbutton(
            container,
            text="Don't show this again",
            variable=dont_show_var,
        ).pack(anchor="w", pady=(0, 14))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x")

        def proceed() -> None:
            result["continue"] = True
            if dont_show_var.get():
                self.cfg.custom_command_warning_acknowledged = True
                save_config(self.cfg)
            dialog.destroy()

        def cancel() -> None:
            result["continue"] = False
            dialog.destroy()

        ttk.Button(buttons, text="Cancel", command=cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Continue", command=proceed, style="Accent.TButton").pack(side="right")

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        dialog.protocol("WM_DELETE_WINDOW", cancel)

        self.root.wait_window(dialog)
        return bool(result["continue"])

    def maybe_show_server_chat_essentials_warning(self) -> bool:
        if self.cfg.server_chat_essentials_warning_acknowledged:
            return True

        dialog = tk.Toplevel(self.root)
        dialog.title("Server Chat Requirement")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=self.colors["bg"])

        result = {"continue": False}
        dont_show_var = tk.BooleanVar(value=False)

        container = ttk.Frame(dialog, padding=18)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Essentials is required for Server Chat.",
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            container,
            text=(
                "This tool sends server chat through Torch Remote's command endpoint using the Essentials "
                "say command. Install and enable the Essentials plugin on the Torch server before using this."
            ),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w", pady=(0, 10))

        link = ttk.Label(
            container,
            text="Open Essentials plugin page",
            style="Link.TLabel",
            cursor="hand2",
        )
        link.pack(anchor="w", pady=(0, 12))
        link.bind("<Button-1>", lambda _event: webbrowser.open("https://torchapi.com/plugins/view/5f02d2a4-1a4b-4cde-9a10-14b2ad8fc7d5"))

        ttk.Checkbutton(
            container,
            text="Don't remind me again",
            variable=dont_show_var,
        ).pack(anchor="w", pady=(0, 14))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x")

        def proceed() -> None:
            result["continue"] = True
            if dont_show_var.get():
                self.cfg.server_chat_essentials_warning_acknowledged = True
                save_config(self.cfg)
            dialog.destroy()

        def cancel() -> None:
            result["continue"] = False
            dialog.destroy()

        ttk.Button(buttons, text="Cancel", command=cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Continue", command=proceed, style="Accent.TButton").pack(side="right")

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        dialog.protocol("WM_DELETE_WINDOW", cancel)

        self.root.wait_window(dialog)
        return bool(result["continue"])


    def send_server_chat(self) -> None:
        if not self.refresh_client():
            return

        message = self.server_chat_var.get().strip()
        if not message:
            return

        if not self.maybe_show_server_chat_essentials_warning():
            torch_info("Server chat message canceled.")
            return

        endpoint = self.cfg.command_endpoint or COMMAND_ENDPOINT
        quoted = quote_command_text(message)

        command_variants = [
            f"say {quoted}",
            f"!say {quoted}",
        ]

        self.server_chat_var.set("")

        def task() -> None:
            for command in command_variants:
                body: dict[str, Any] = {
                    "command": command,
                    "streamed": True,
                    "streamingDuration": "00:00:10",
                }

                try:
                    torch_info(
                        "Server Chat:\n"
                        f"  message: {message}"
                    )

                    resp = self.client.request_with_policy(
                        "POST",
                        endpoint,
                        json_body=body,
                        timeout_override=20.0,
                    )

                    if 200 <= resp.status_code < 300:
                        torch_success("Server Chat: Message sent successfully.")
                        return

                    if resp.status_code in (401, 403):
                        torch_error("Server Chat: Authorization failed.")
                        return

                    if resp.status_code == 404:
                        torch_error("Server Chat: Command endpoint returned 404.")
                        return

                    torch_warning(f"Server Chat: command variant failed with HTTP {resp.status_code}; trying fallback if available.")

                except requests.RequestException as exc:
                    torch_error(f"Server Chat: message failed.\n  {exc}")
                    return
                except Exception as exc:
                    torch_error(f"Server Chat: unexpected client error.\n  {exc}")
                    return

            torch_error("Server Chat: message was not accepted by any command variant.")

        self.run_worker(task)

    def set_and_send(self, command: str) -> None:
        self.command_var.set(command)
        self.send_command()

    def send_command(self) -> None:
        if not self.refresh_client():
            return

        command = self.command_var.get().strip()
        if not command:
            return

        if not self.maybe_show_custom_command_warning():
            logger.warning("Command canceled by user.")
            return

        streamed = bool(self.stream_command_var.get())

        try:
            seconds = int(float(self.command_stream_duration_var.get().strip() or "15"))
        except ValueError:
            seconds = 15

        seconds = max(1, min(seconds, 60))

        body: dict[str, Any] = {"command": command}
        if streamed:
            body["streamed"] = True
            body["streamingDuration"] = f"00:00:{seconds:02d}"

        endpoint = self.cfg.command_endpoint or COMMAND_ENDPOINT

        def task() -> None:
            timeout = command_timeout_seconds(streamed, seconds, self.cfg.timeout_seconds)

            try:
                torch_info(
                    f"POST {endpoint}\n"
                    f"  command: {command}\n"
                    f"  streamed: {streamed}\n"
                    f"  timeout: {timeout:.1f}s"
                )

                resp = self.client.request_with_policy(
                    "POST",
                    endpoint,
                    json_body=body,
                    timeout_override=timeout,
                )
                log_response(resp, endpoint)

                if resp.status_code == 405:
                    torch_error("Command route exists but rejected method. This should be POST.")
                elif 200 <= resp.status_code < 300 and not streamed:
                    torch_success("Command accepted.")
                    torch_info("Non-streamed command may return only a UUID/handle.")

            except requests.exceptions.ReadTimeout:
                torch_warning(
                    "Command request timed out while waiting for streamed output.\n"
                    f"  command: {command}\n"
                    f"  streamed duration: {seconds}s\n"
                    f"  client timeout: {timeout:.1f}s\n"
                    "The command may still have executed server-side."
                )
            except requests.RequestException as exc:
                torch_error(f"Command request failed:\n  {exc}")
            except Exception as exc:
                torch_error(f"Unexpected command client error:\n  {exc}")

        self.run_worker(task)


    def send_rest_shortcut(self, method: str, endpoint: str) -> None:
        if not self.refresh_client():
            return

        def task() -> None:
            try:
                torch_info(f"{method.upper()} {endpoint}")
                resp = self.client.request_with_policy(method, endpoint)
                log_response(resp, endpoint)

                if resp.status_code in (401, 403):
                    torch_error("Authorization failed.")
                elif resp.status_code == 404:
                    torch_error("Endpoint returned 404. Check Torch Remote routes/version.")
                elif not (200 <= resp.status_code < 300):
                    torch_warning(f"Unexpected HTTP {resp.status_code}.")
            except requests.RequestException as exc:
                torch_error(f"REST request failed:\n  {exc}")
            except Exception as exc:
                torch_error(f"Unexpected REST client error:\n  {exc}")

        self.run_worker(task)


    def check_server_ready_on_startup(self) -> None:
        if not self.cfg.host.strip() or not self.cfg.token.strip():
            return

        if not self.refresh_client():
            return

        def task() -> None:
            try:
                resp = self.client.get(STATUS_ENDPOINT)

                if resp.status_code == 200:
                    torch_success("Server Ready: status API responded 200.")
                elif resp.status_code in (401, 403):
                    torch_warning("Server Ready: authorization failed.")
                elif resp.status_code == 404:
                    torch_warning("Server Ready: status endpoint returned 404.")
                else:
                    torch_warning(f"Server Ready: unexpected HTTP {resp.status_code}.")
            except requests.RequestException as exc:
                torch_warning(f"Server Ready: connection check failed.\n  {exc}")

        self.run_worker(task)


    def test_connection(self) -> None:
        if not self.refresh_client():
            return

        def task() -> None:
            try:
                resp = self.client.get(STATUS_ENDPOINT)

                if resp.status_code == 200:
                    torch_success("Test: Passed. Response 200.")
                    return

                if resp.status_code in (401, 403):
                    torch_error(f"Test: Failed. Authorization returned {resp.status_code}.")
                    return

                if resp.status_code == 404:
                    torch_error("Test: Failed. Status endpoint returned 404.")
                    return

                torch_warning(f"Test: Failed. Unexpected HTTP {resp.status_code}.")

            except requests.RequestException as exc:
                torch_error(f"Test: Failed. Could not connect.\n  {exc}")

        self.run_worker(task)

    def probe_routes(self) -> None:
        if not self.refresh_client():
            return

        endpoints = [
            STATUS_ENDPOINT,
            SERVER_SETTINGS_ENDPOINT,
            PLAYERS_ENDPOINT,
            BANNED_PLAYERS_ENDPOINT,
            PLUGINS_ENDPOINT,
            PLUGIN_DOWNLOADS_ENDPOINT,
            SELECTED_WORLD_ENDPOINT,
            SETTINGS_KEYS_ENDPOINT,
        ]

        def task() -> None:
            torch_info("Checking Torch Remote REST endpoints...")
            for ep in endpoints:
                try:
                    resp = self.client.get(ep)
                    log_response(resp, ep)

                    if resp.status_code in (401, 403):
                        torch_error("Authorization failed. Stopping endpoint check.")
                        return

                    if resp.status_code == 404:
                        torch_error("Endpoint returned 404. Stopping endpoint check.")
                        return

                    if not (200 <= resp.status_code < 300):
                        torch_warning(f"Unexpected HTTP {resp.status_code}. Stopping endpoint check.")
                        return

                except requests.RequestException as exc:
                    torch_error(f"Endpoint check failed. Stopping.\n  {exc}")
                    return

            torch_success("Endpoint check completed.")

        self.run_worker(task)

    def on_close(self) -> None:

        try:

            self.save_from_ui()

        except Exception:

            pass


        self.root.destroy()


def main() -> int:

    root = tk.Tk()

    App(root)

    root.mainloop()

    return 0


if __name__ == "__main__":

    raise SystemExit(main())
