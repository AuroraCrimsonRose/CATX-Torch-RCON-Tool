# CATX Systems Torch RCON Tool

Windows admin client for Torch Remote-enabled Space Engineers servers.

## Requirements

Server-side:

- Space Engineers dedicated server
- Torch
- Torch Remote plugin
- Essentials plugin for Server Chat messages
- Reachable Torch Remote HTTP listener

Client-side:

- Windows 10/11
- Python 3.11+ for source runs, or the packaged EXE

WebSockets are not required.

## Torch Remote endpoints used

```text
GET  /api/v1/server/status
GET  /api/v1/server/settings
GET  /api/v1/players
GET  /api/v1/players/banned
GET  /api/v1/plugins
GET  /api/v1/plugins/downloads/
GET  /api/v1/worlds/selected
GET  /api/v1/settings/
POST /api/v1/chat/command
```

The app uses the `SecurityKey` from `Instance/TorchRemote.cfg` as a Bearer token.

Server Chat uses `/api/v1/chat/command` with `say` because `/api/v1/chat/message` can throw `VRage.Network.ChatMsg.CustomAuthorName` compatibility errors on some Torch/Space Engineers versions.

## Run from source

```powershell
python -m pip install loguru requests keyring
python .\main.py
```

## Build EXE

Place `logo.png` next to `main.py` if you want a custom icon.

```powershell
.\build.ps1
```

Output:

```text
dist\CATX-Systems-Torch-RCON-Tool.exe
```

## Self-sign development EXE

```powershell
.\self_sign_dev.ps1
```

Self-signing does not create SmartScreen reputation. It is mostly useful for testing and tamper indication.

## Build installer

Install Inno Setup 6, then run:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" .\installer.iss
```

## App data

```text
%LOCALAPPDATA%\CATX\TorchRemoteAdmin\
├─ Settings\
│  └─ torch_config.json
└─ Logs\
   ├─ latest.log
   └─ torch_latest.log
```

The SecurityKey is stored through OS credential storage via `keyring`; the JSON config does not store the plaintext key.

## License

This project is source-available under the CATX Source-Available License 1.0.

You may use, fork, and modify the code. If you redistribute it, you must remove or replace CATX Systems LLC / Aurora Tejeda branding, logos, icons, and names unless you have explicit written permission.
