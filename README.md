# Tieba_Sign

An automated Baidu Tieba daily sign-in script based on the mobile API flow extracted from [`0ranko0P/TiebaLite`](https://github.com/0ranko0P/TiebaLite).  
It is designed for a normal GitHub repository and can run on GitHub Actions on a schedule.

Unlike web click-based sign tools, this project keeps the final sign flow on the mobile API side.  
Web QR login is only used locally to export login material such as `BDUSS`, `STOKEN`, and `BAIDUID`.

## 1. Introduction

### 1.1 What this project does

This project signs into Tieba through the mobile API and can be scheduled with GitHub Actions.

The workflow is:

1. Log into Tieba locally through a QR code
2. Export `tieba_cookies.json`
3. Save that JSON into GitHub Secrets
4. Run `main.py` on GitHub Actions
5. Complete sign-in through the mobile API flow

### 1.2 Repository layout

```text
Tieba_Sign/
├─ .github/workflows/
│  └─ sign.yml
├─ client.py
├─ login.py
├─ service.py
├─ main.py
├─ requirements.txt
└─ README.md
```

Core files:

- `login.py`
  - exports `tieba_cookies.json` through a local QR login
  - reads login material from environment variables or a local cookie file
- `client.py`
  - implements the TiebaLite-style mobile request profile
  - performs `login + initNickname + forumGuide + getforumlist + msign/sign`
- `service.py`
  - coordinates the complete sign-in workflow
  - falls back from `msign` to normal per-forum `sign` when needed
- `main.py`
  - entrypoint for the actual sign task

## 2. Requirements

You need:

- a Tieba account that can log in normally
- a network environment that can access GitHub
- a local Python environment for the one-time cookie export step
- a local browser such as Chrome or Edge for QR login

## 3. Quick Start

### 3.1 Fork the repository

Fork this repository to your own GitHub account.

### 3.2 Install dependencies

For the sign task:

```bash
python -m pip install -U pip
python -m pip install -r requirements.txt
```

For local QR login and cookie export:

```bash
python -m pip install -r requirements-login.txt
```

For tests:

```bash
python -m pip install -r requirements-dev.txt
pytest
```

### 3.3 Export cookies locally

Run:

```bash
python login.py
```

The script will:

- open Tieba in a local browser
- wait for you to complete QR login
- export `tieba_cookies.json` in the current directory
- verify whether `BDUSS`, `STOKEN`, and `BAIDUID` were found

If the browser path cannot be detected automatically, set it manually:

```powershell
$env:TIEBA_BROWSER_PATH='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
python login.py
```

### 3.4 Configure GitHub Secrets

Go to:

`Settings -> Secrets and variables -> Actions`

Recommended minimal setup:

- `TIEBA_COOKIES`

The value should be the full JSON content of `tieba_cookies.json`.

The script automatically extracts:

- `BDUSS`
- `STOKEN`
- `BAIDUID`

Optional secrets:

- `TIEBA_BDUSS`
- `TIEBA_STOKEN`
- `TIEBA_BAIDUID`
- `TIEBA_DEVICE_SEED`
- `TIEBA_BROWSER_PATH`

Optional variables:

- `TIEBA_USE_OFFICIAL_MSIGN=true`
- `TIEBA_SLOW_MODE=false`
- `TIEBA_SIGN_DELAY_MS=2000`
- `TIEBA_FAIL_ON_PARTIAL_FAILURE=false`
- `TIEBA_REQUEST_TIMEOUT=30`
- `TIEBA_DRY_RUN=false`

### 3.5 Run the workflow

The workflow file is [`.github/workflows/sign.yml`](.github/workflows/sign.yml).

Default trigger options:

- manual run through `workflow_dispatch`
- scheduled run every day at `01:30 UTC`
- equivalent to `09:30` in `Asia/Shanghai`

The workflow runs:

```bash
python main.py
```

### 3.6 Run locally

If `tieba_cookies.json` exists in the project root, you can run the real sign flow directly:

```bash
python main.py
```

`main.py` will automatically use:

1. `TIEBA_COOKIES`
2. `TIEBA_COOKIE_FILE`
3. `tieba_cookies.json` in the project root

You can also provide login material directly through environment variables:

- `TIEBA_COOKIES`
- `TIEBA_BDUSS`
- `TIEBA_STOKEN`
- `TIEBA_BAIDUID`

## 4. How It Works

### 4.1 Cookie loading

`login.py` reads login material from environment variables first and then falls back to a local cookie file.

Priority:

1. `TIEBA_COOKIES`
2. `TIEBA_COOKIE_FILE`
3. `tieba_cookies.json`

### 4.2 Browser startup for QR login

`login.py` uses `DrissionPage` to start a local browser session, open Tieba, and wait for QR login.

It also:

- tries to detect a browser automatically
- supports manual override with `TIEBA_BROWSER_PATH`
- uses an isolated temporary browser profile
- disables extensions and first-run noise as much as possible

### 4.3 Mobile login authentication

`client.py` does not use the web sign flow.

Instead, it uses mobile API requests modeled after TiebaLite for:

- `login`
- `initNickname`
- `forumGuide`
- `getforumlist`
- `msign`
- `sign`

This is the core reason the repository is built around a mobile sign-in flow instead of a normal web click flow.

### 4.4 Forum list loading

The script fetches liked forums through `forumGuide`, then gets official multi-sign limits through `getforumlist`.

### 4.5 Sign strategy

The sign process works like this:

1. try `msign` for forums that match the official conditions
2. if `msign` fails for any forum, fall back to normal `sign`
3. keep recording per-forum failures without discarding the rest of the run

### 4.6 Exit behavior

- normal partial failures do not stop the whole run by default
- network-level failures stop the process
- if `TIEBA_FAIL_ON_PARTIAL_FAILURE=true`, partial sign failures return a non-zero exit code

## 5. Notes

- This is a mobile API sign-in flow, not a web click-sign flow.
- Cookies are only used to obtain login material.
- `STOKEN` is required for the full mobile flow.
- `tieba_cookies.json` is ignored by `.gitignore` and should never be committed.
- Real cookie data should only be stored in GitHub Secrets, not in source files or documentation.
