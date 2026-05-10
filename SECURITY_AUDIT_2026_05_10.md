# Security Audit — pdfconverter
**Date:** 2026-05-10
**Auditor:** automated review
**Scope:** Full codebase scan (Python FastAPI + JS templates), excluding the 4 issues already documented in `CHROME_EXTENSION_ROADMAP.md` (DNS rebinding, cross-origin CSRF on loopback, missing CSP, no rate limiting).

The codebase is a LAN-first all-in-one PDF tool that binds `0.0.0.0:8000` by default. Loopback callers bypass auth; remote callers must present `mobile_token`. Every finding below assumes the threat model where (a) the operator's own browser may visit a hostile site, and (b) anyone on the same LAN can see the listener.

---

## Critical findings

### C1 — `/pdf/from-url` SSRF guard bypassed by HTTP redirects
- **Severity:** Critical
- **Location:** `core/converters.py:363-397` (`url_to_pdf`)
- **Description:** The function calls `core._assert_public_url(parsed)` on the URL the user supplied, but then passes the raw URL to `urllib.request.urlopen(req, ...)`. `urlopen` follows HTTP 302/301 redirects automatically and does **not** re-run `_assert_public_url` on the redirect target. An attacker controlling any public host can serve `Location: http://127.0.0.1:8000/admin/clamav-update` and the server will follow it from inside the trust boundary.
- **Exploit scenario:** Attacker hosts `http://attacker.com/redirect.php` returning `302 Location: http://169.254.169.254/latest/meta-data/` (or `http://127.0.0.1:8000/admin/enable-mobile`). They submit `https://attacker.com/redirect.php` to `/pdf/from-url`. The server fetches the redirect target from the loopback context — bypassing the loopback gate the middleware enforces for remote clients. On a cloud host this also reaches the cloud-metadata service.
- **Combined with the existing TOCTOU window:** even without redirects, DNS rebinding lets a hostile DNS server return a public IP on the `getaddrinfo` call and a private IP on the `urlopen` call. The redirect path is the bigger hole because it doesn't even need DNS games.
- **Fix:** Use a custom `HTTPRedirectHandler` (or `urllib3`/`httpx` with redirect callback) that validates every redirect target through `_assert_public_url` before following. Also consider `socket_options` to bind the resolver result and pass the resolved IP via `Host:` header (pinning), neutralising both redirect bypass and DNS rebinding in one shot.
- **Notes:** Reachable from any client that can hit `/pdf/from-url`. Even with the mobile-auth middleware, the **operator's own browser** is loopback, so a hostile page in the operator's browser can drive this — and combined with cross-origin CSRF (already noted) any web page the operator visits can drive it via cross-origin POST.

### C2 — `clamav_update` runs `freshclam` over plaintext mirror
- **Severity:** High → Critical depending on threat model
- **Location:** `core/clamav_update.py:162-227` (`update_signatures`); `clamav/freshclam.conf` (bundled, not read here)
- **Description:** ClamAV signature databases default to fetching from `database.clamav.net` over HTTP (cisco does sign DBs but `freshclam` historically defaults to plaintext mirror selection; HTTPS support exists but is conf-driven). The bundled `freshclam.conf` is treated as an opaque file — this audit could not verify its contents from grep-able sources, so this finding **needs verification**. If `freshclam.conf` allows plaintext fallback or unsigned DB acceptance, an on-path attacker on the user's LAN/ISP can ship a malicious `daily.cvd`. ClamAV does verify CVD signatures against bundled CA, mitigating this — but verify the bundled `freshclam.conf` enforces HTTPS-only and that the embedded DigSig anchor is current.
- **Fix:** Verify `freshclam.conf` contains `DatabaseMirror https://database.clamav.net` (note `https`) and not the bare http variant; pin to known-good mirrors; document expected behaviour. Optionally pin `cvdcertsdir` and refuse on signature failure.
- **Status:** **needs verification** — read the bundled `clamav/freshclam.conf` to confirm.

### C3 — `/pdf/from-url` and `/pdf/from-html` have no response/HTML size cap
- **Severity:** High
- **Location:** `core/converters.py:382-390` (`urlopen(...).read()`)
- **Description:** `raw = resp.read()` reads the entire HTTP response into memory with no cap. An attacker (or just a misconfigured site) can serve a multi-GB stream and OOM the process. Same for `/pdf/from-html` — `html` is a `Form()` field; the only check is `len(html.encode("utf-8")) > MAX_UPLOAD_MB * 1024 * 1024` which uses the upload cap (default 2048 MB → 2 GB of HTML in RAM is huge).
- **Fix:** Cap `urlopen.read()` at e.g. 50 MB (HTML rarely exceeds this). For `/pdf/from-html` lower the cap dramatically (5–10 MB).

### C4 — Job-token tied endpoints create directories before validating the token
- **Severity:** High
- **Location:** `routers/batch.py:524, 585, 638`; `core/files.py:43-60` (`make_job_dir`)
- **Description:** Several endpoints call `core.make_job_dir("jobs", token)` **before** any `check_token` runs. `make_job_dir` calls `WORK_DIR.joinpath("jobs", token).mkdir(parents=True, exist_ok=True)` and only then runs `assert_under_work`. If the token contains path separators (`..\\foo`, `..%2Ffoo`, absolute path on Windows), `mkdir` runs first and may create unintended directories before the resolve-check fires. On Windows, `Path.joinpath` interprets backslashes as separators, and `joinpath("..\\evil")` resolves outside `WORK_DIR/jobs`. `assert_under_work` raises 500, but partial dir creation may have happened and an attacker can DoS the disk by spamming arbitrary tokens (each request creates a new subdir under `_work/jobs/`).
- **Affected endpoints (no `check_token` before `make_job_dir`):**
  - `GET /batch-download/{token}` — line 524
  - `POST /batch-distribute/{token}` — line 585
  - `GET /batch-distribute/{token}/download` — line 638
  Although `load_job` / `load_distribution` later calls `check_token`, the directory creation already happened.
- **Fix:** Always call `core.check_token(token)` as the very first line of every endpoint that takes a token in the URL. Move the validation into `make_job_dir` itself for any caller that passes a `parts[-1]` which originates from a user-controlled string.
- **Note:** `make_job_dir` should also `assert_under_work` *before* `mkdir`, by computing `path.resolve()` on a hypothetical `WORK_DIR / parts` and refusing if it's outside, then mkdir.

### C5 — `/pdf/edit/save` and the entire `/pdf/*` (non-convert) tool family bypass `gate_pdf_safety`
- **Severity:** High
- **Location:** `routers/pdf_tools.py` (every endpoint), `routers/editor.py`
- **Description:** `gate_pdf_safety` is invoked only by `/convert` (sync), `/ocr-start`, and the async convert/batch workers. Every PDF tool endpoint accepts uploads with **no** safety check: `/pdf/merge`, `/pdf/split`, `/pdf/compress`, `/pdf/encrypt`, `/pdf/decrypt`, `/pdf/watermark-text`, `/pdf/watermark-image`, `/pdf/page-numbers`, `/pdf/header-footer`, `/pdf/crop`, `/pdf/rotate`, `/pdf/reorder`, `/pdf/delete-pages`, `/pdf/from-images`, `/pdf/to-markdown`, `/pdf/to-csv`, `/pdf/from-docx`, `/pdf/from-xlsx`, `/pdf/find`, `/pdf/outline`, `/pdf/metadata`, `/pdf/set-metadata`, `/pdf/extract-images`, `/pdf/thumbnail`, `/pdf/deep-analyze`, `/pdf/extractability`, `/pdf/detect-blank`, `/pdf/remove-blank`, `/pdf/detect-signatures`, `/pdf/classify`, `/pdf/batch`, `/pdf/edit/spans`, `/pdf/edit/save`. PyMuPDF and `pdf2docx` are called on raw user input directly.
- **Exploit scenario:** A malicious PDF with `/JavaScript`, `/Launch`, embedded files, or a parser-bomb structure (deeply nested object refs, recursive XObject, oversize images) can crash the worker, exhaust RAM, or trigger CVE behaviour in PyMuPDF/MuPDF. Even if no current PyMuPDF CVE is exploitable, the *whole point* of `pdf_safety_scan` is defense in depth, and 30+ endpoints skip it.
- **Fix:** Add `gate_pdf_safety(in_path)` after `save_pdf_upload(...)` in every `/pdf/*` endpoint. The `pdf_response` ride-along makes this a one-line addition per route.

---

## High findings

### H1 — Self-signed cert generation uses deprecated `datetime.utcnow()` and weak SAN logic
- **Severity:** Medium-High
- **Location:** `core/network.py:60-106` (`ensure_self_signed_cert`)
- **Description:**
  - `datetime.utcnow()` is deprecated in Python 3.12+ (returns naive datetime). The cert builder's `not_valid_before/after` should be timezone-aware (`datetime.now(timezone.utc)`).
  - `not_valid_after` is `+5 years` — far longer than CA/B baseline 397 days for trusted certs, fine for self-signed local but rotation is impossible without manual cleanup of `cert/`.
  - SAN includes `lan_ip()` resolved at boot. If the machine's IP changes (DHCP), the cert no longer matches and the operator either downgrades to HTTP or accepts a confusing TLS warning. Worse: the cert file is reused on every reboot — the private key never rotates.
- **Fix:** Use `datetime.now(timezone.utc)`, regenerate the cert annually (compare not-valid-after on startup; rebuild if <30d remaining), and add a SAN for every interface IP, not just one.

### H2 — `mobile_token` accepted from `?key=` URL parameter
- **Severity:** High (operational), already partially noted in extension roadmap but worth re-flagging
- **Location:** `app.py:262`, `routers/admin.py:35`
- **Description:** The middleware accepts `?key=<token>` as a fallback when `X-Mobile-Key` is missing. The `enable_mobile` endpoint *returns a URL containing the token in the query string*: `f"{scheme}://{lan}:{port}/?key={token}"`. This URL ends up in:
  - the operator's clipboard (they paste it to their phone — fine),
  - the **mobile browser's history** (persistent across sessions),
  - **server access logs** (uvicorn logs the URL with `?key=…`),
  - **HTTP referer headers** sent to any third-party resource the page later loads.
  Any process that scrapes browser history, any admin reading the access log, or any third-party CDN that the page references gets the live token.
- **Fix:** Stop accepting `?key=` fallback. Require `X-Mobile-Key` header. The first-time mobile setup can use a one-time entry page that takes the key in a form field and stores it in `localStorage`; subsequent requests attach it via a JS fetch wrapper. Also, scrub `?key=` from access logs (custom uvicorn log filter).

### H3 — `client_ip` X-Forwarded-For trust list does not match `is_local_request`
- **Severity:** Medium-High
- **Location:** `core/network.py:17-44`
- **Description:** `client_ip` honours `X-Forwarded-For` only when the immediate peer is in `HT_TRUSTED_PROXIES`. Good. But `is_local_request` checks `request.client.host in LOCAL_HOSTS` — it does NOT honour `HT_TRUSTED_PROXIES`. So if you run behind a reverse proxy on the same machine (e.g., nginx on 127.0.0.1 forwarding from public LAN), every remote request looks "local" and bypasses the mobile-token gate.
- **Exploit:** Any operator who wants TLS termination at nginx and forwards to `127.0.0.1:8000` instantly opens loopback bypass to the world. The README does not warn about this.
- **Fix:** Either (a) add a documented warning that the app must NOT be reverse-proxied without the operator setting `HT_TRUSTED_PROXIES` and rewriting `is_local_request` to consult X-Forwarded-For only from trusted proxies, **and** the original X-Forwarded-For must point to a loopback IP; or (b) introduce a `HT_LOOPBACK_BYPASS=false` switch that disables the auto-pass for loopback so every client must present a token.

### H4 — `/health` endpoint is unauthenticated and discloses operational telemetry
- **Severity:** Medium-High
- **Location:** `app.py:297-340` (`/health` is in `_MOBILE_PUBLIC_PATHS`)
- **Description:** `/health` returns:
  - app version,
  - uptime seconds (lets attackers know if a restart happened),
  - `thread_count` (drift over time reveals load),
  - `work_dir_bytes` / `work_dir_files` (lets attackers gauge how much processing is in flight),
  - `disk_free_bytes`,
  - per-kind running/total counters.
  These are useful for ops but — combined with cross-origin CSRF — let any web page profile the operator's environment from the browser without auth.
- **Fix:** Trim `/health` to `{ok: true, version}` for public. Move detailed stats behind `is_local_request` (or behind the mobile token).

### H5 — `_PROCESS_STARTED_AT` and `/health` reveal version + uptime to LAN scans
- Same as H4. Specifically the `__version__` field gives an attacker a precise version → CVE database lookup. Either omit version or only reveal to authenticated callers.

### H6 — `clamd.exe` spawned with no resource limits
- **Severity:** Medium-High
- **Location:** `core/clamav_daemon.py:255-263`
- **Description:** `clamd` is started without setting Job objects (Windows) or rlimits (POSIX). `clamd.conf` does set `MaxFileSize 200M`, `MaxScanSize 400M`, `MaxRecursion 10`, `MaxFiles 10000`, `MaxThreads 4` — these are reasonable. However, `clamd` runs as the same user as the app (no privsep), so a successful `clamd` exploit (rare but historical CVEs exist) gets app-level access. On Windows, no Job object means a runaway clamd can consume the entire host's RAM despite `MaxScanSize`.
- **Fix:** On Windows, attach `clamd.exe` to a `Job` object with memory caps via `ctypes`/`pywin32`. On Linux, use `prlimit` or systemd's slice.

### H7 — `/admin/clamav-update` triggers freshclam network fetch from any local-loopback caller
- **Severity:** Medium-High (combined with cross-origin CSRF: High)
- **Location:** `routers/admin.py:84-108`
- **Description:** Local-only check uses `is_local_request`. With cross-origin CSRF (already noted but re-emphasising) any web page in the operator's browser can issue a POST to `/admin/clamav-update`, kicking off a 300 MB download. No throttle beyond `should_update()`'s 24h check, which the endpoint **bypasses by force**.
- **Fix:** Require X-Mobile-Key for mutating admin endpoints even on loopback (operator's browser is loopback too).

### H8 — `/admin/enable-mobile` issues a token from any loopback caller
- **Severity:** High (combined with cross-origin CSRF: Critical)
- **Location:** `routers/admin.py:23-44`
- **Description:** Same pattern as H7. The operator's browser visits `evil.com`, evil.com submits a POST to `http://127.0.0.1:8000/admin/enable-mobile`, the server happily mints a `mobile_token` and **returns it in the JSON response**. Browser fetch CORS prevents reading the body cross-origin **unless** the page uses `mode: no-cors` (in which case it writes but can't read), or unless the response has a permissive `Access-Control-Allow-Origin` (it doesn't). So a remote attacker can't directly read the new token — but they can **rotate** an existing token, locking the legitimate phone out (DoS).
- More subtle: the response *also* contains `lan_ip` and `port` — useful for an attacker who got the token via another channel.
- **Fix:** Require an explicit confirmation step (CSRF token in a hidden form field), **and/or** require `Origin: <loopback-only>` validation in the endpoint.

### H9 — No SSRF re-check on `_assert_public_url` itself: TOCTOU window
- Already documented in the source comment but worth restating: the gap between `getaddrinfo` and `urlopen` is wide (multiple ms). A local DNS resolver poisoned to return public IP on first call and `127.0.0.1` on second is realistic via DNS rebinding (TTL=0). Even without redirect bypass (C1), this is exploitable.
- **Fix:** Resolve once, then connect by IP and pass the original hostname via `Host:` header. The `requests` library has community SSRF wrappers for this; stdlib needs a custom `HTTPConnection` subclass.

### H10 — `ensure_self_signed_cert` uses `cryptography` with `SHA256` but no SAN for hostname
- See H1 for full breakdown.

---

## Medium findings

### M1 — Path traversal hardening in `safe_filename` is incomplete on Unicode
- **Location:** `core/files.py:16-24`
- The regex `[\\/:*?\"<>|]+` strips ASCII separators, then `\.{2,}` collapses `..` runs. But Unicode normalisation is not applied, so a name like `..‮/foo` (right-to-left override) or `‥/foo` (U+2025 two-dot leader) might not be canonicalised. On NTFS these mostly become literal filenames not traversal, but they confuse any downstream code that reads the filename as display text.
- **Fix:** `unicodedata.normalize("NFKC", name)` before applying the strip; reject any name containing control chars `\x00-\x1f`.

### M2 — `pdf_safety.check_structure` reads only first/last 4 MB of large PDFs
- **Location:** `pdf_safety.py:101-108`
- A malicious PDF can hide `/JavaScript` in the middle of an 8+ MB stream and the structural scan will miss it. This is mitigated by ClamAV (full scan) and pdfid.py (decompression-aware), but if both are missing, big payloads slip through.
- **Fix:** When the file is >8 MB, rely solely on the structural scan as a signal, but log a warning and require ClamAV/pdfid presence (or fall through to an explicit "warning" verdict).

### M3 — `history_db.py` re-uses one connection across threads with `check_same_thread=False`
- **Location:** `core/history_db.py:43`
- The connection is shared via `_history_lock`. The lock makes it safe, but if a future change forgets the lock, you get DB corruption. Defense: switch to `threading.local`-scoped connections, or use SQLite `connection.isolation_level = None` with explicit BEGIN.

### M4 — `history_clear` (`DELETE /history`) has no auth at all
- **Location:** `routers/history.py:51-59`
- Anyone who can reach the endpoint can wipe the entire audit trail. Combined with cross-origin CSRF, any web page the operator visits can wipe history. The audit log is the *only* record of who used the tool — destroying it covers the attacker's tracks after they CSRF other endpoints.
- **Fix:** Gate behind mobile-token (or local-only + CSRF token).

### M5 — `xlsx_to_pdf` uses `openpyxl` with `read_only=True`, but processes formulas
- **Location:** `core/converters.py:545`
- `data_only=True` reads cached values (fine, no formula injection). However, `openpyxl` parses XML — historically not vulnerable to XXE because `openpyxl` uses `defusedxml` internally for >=3.0. Verify `openpyxl>=3.1` doesn't regress; `pyproject.toml` pins `openpyxl>=3.1,<4.0` — likely safe but **needs verification** the bundled wheel uses defusedxml.

### M6 — `xhtml2pdf` HTML rendering reads HTML attacker-controlled
- **Location:** `core/converters.py:_xhtml2pdf_render`
- xhtml2pdf historically had XXE in `<link>` and `<img src=>` URL fetching. The `link_callback` here overrides URL resolution, but does it for `ht-font://` only — generic `http://`/`file://` URLs are still processed by the default fetcher which **can read local files** (`file:///etc/passwd`).
- **Exploit:** User submits HTML `<img src="file:///c/Windows/win.ini">` to `/pdf/from-html`; xhtml2pdf reads the file and embeds its bytes. The PDF then leaks local file content. Same applies to `/pdf/from-url` since that pipeline ends in `html_to_pdf`.
- **Fix:** Override `link_callback` to refuse `file://` and any `http://` host that fails `_assert_public_url`. Alternative: pre-strip `<img>`, `<link>`, `<object>`, `<embed>`, `<iframe>` from the HTML before render.
- **Status:** **needs verification** but very likely exploitable — xhtml2pdf default behaviour is well-documented to fetch local files.

### M7 — `/pdf/from-url` `User-Agent` is hardcoded; HTTP basic-auth in URL accepted
- `Request(url, ...)` passes the URL as-is. `urllib.request` honours `user:pass@host` in URLs. Possibly intentional, but lets the server be tricked into authenticating to internal services it has creds for.

### M8 — Background threads spawned per request are unbounded
- **Location:** `routers/convert.py:192`, `routers/batch.py:223,383`, `routers/ocr.py:69`, `routers/admin.py:107`
- Every `/convert-start`, `/batch-files`, `/batch-convert`, `/ocr-start`, `/admin/clamav-update` spawns a `threading.Thread`. There's no global cap and no queue — a flood of requests creates unbounded threads. With Python's GIL and PyMuPDF holding native handles, this exhausts file descriptors and worker memory long before the scheduler does.
- **Fix:** Use a bounded `ThreadPoolExecutor` (e.g., `max_workers=4`) and `submit()` to it; reject (HTTP 503) when the queue is full. Pair with `MAX_INFLIGHT_JOBS` setting.

### M9 — `MAX_UPLOAD_MB` default 2048 (2 GB) per file
- **Location:** `settings.py:51`
- 2 GB is ~10× larger than any reasonable PDF. With 10 concurrent uploads streaming chunks, you can write 20 GB to disk before the cap kicks in. Combined with M8 (unbounded thread spawn), this is a quick disk-fill DoS.
- **Fix:** Default 200 MB; make 2 GB an explicit opt-in.

### M10 — `pdfid.py` invoked via subprocess with `python` resolved from PATH
- **Location:** `pdf_safety.py:306` — `cmd = ["python", exe, str(pdf_path)] if exe.endswith(".py") else ...`
- `"python"` is resolved against `PATH`. On a poisoned host with a hostile `python.exe` earlier in PATH, the safety scanner runs attacker code. Should use `sys.executable`.
- **Fix:** Replace `"python"` with `sys.executable`.

### M11 — `_find_unicode_font` reads arbitrary system font paths
- **Location:** `core/pdf_tools.py:30-65`
- Hardcoded candidate paths include `C:/Windows/Fonts/arial.ttf`, etc. These are read with `Path.exists()` and then their bytes are loaded by reportlab/PyMuPDF. Not user-controllable; not a finding by itself, but worth noting that font caching is keyed on the first-found candidate per process — symlink swap on a shared host could change behaviour.

### M12 — `core.parse_pdf_for_batch` runs in a `ProcessPoolExecutor` — no resource caps on children
- **Location:** `pipelines/batch_convert.py:300-307`
- Worker children inherit no `setrlimit` or Job object. A pathological PDF that locks one child's `pdf2docx` parser can hang up to `MAX_JOB_TIMEOUT_SECONDS` (30 min) because nothing kills the worker process — `as_completed` blocks forever (no timeout passed to `fut.result()`).
- **Fix:** Pass `fut.result(timeout=N)` and `executor.shutdown(wait=False, cancel_futures=True)` on timeout. Also clamp child memory via `setrlimit(RLIMIT_AS, …)` on POSIX.

### M13 — `parse_int_list` allows huge ranges via `1-99999999`
- **Location:** `app_http.py:134-156`
- `range(start, end+1)` for `1-100000000` materialises 100M ints. With `pdf_rotate`/`pdf_delete_pages` accepting this without page-count validation upstream, a client can OOM the server with one form field.
- **Fix:** Cap range size to e.g. 100k, or reject any range exceeding the actual page count.

### M14 — `templates/index.html` has no CSP `meta` tag (already noted in roadmap, but the inline-script-heavy template makes a strict CSP hard later)
- The template includes massive inline JS. Adding a CSP later will require either `'unsafe-inline'` (defeating the purpose) or a heavy refactor to extract every `<script>` to a hashed/nonced asset.
- **Fix recommendation:** Plan for nonce-based CSP at the same time as adding the header, and migrate inline `<script>`/`<style>` to externals over time.

---

## Low findings / hardening suggestions

### L1 — `state.py` reads `MAX_UPLOAD_MB` env var separately from `settings.max_upload_mb`
- Two sources of truth (`os.environ.get("MAX_UPLOAD_MB")` and `HT_MAX_UPLOAD_MB` via settings). Confusing for ops. Pick one.

### L2 — `is_local_request` uses string comparison against `LOCAL_HOSTS`
- IPv6 zone IDs (`fe80::1%eth0`) wouldn't match `::1`. Fine here since we listed `::1` literal, but be aware that `request.client.host` can include zone suffixes in rare configurations.

### L3 — `disable_mobile` doesn't audit-log
- `enable_mobile` logs token-issuance with length only (good). `disable_mobile` simply logs "Mobile access disabled". For an audit trail, log `client_ip` of who turned it off.

### L4 — `admin/clamav` and `admin/clamav-update` both `is_local_request`-gated, but `mobile-status` is in `_MOBILE_PUBLIC_PATHS`
- `mobile-status` reveals whether mobile access is enabled and whether the requester is local (via `is_local: bool`). Low info leak — fine for the UI's flow but a remote scanner can probe it without auth.

### L5 — `safe_filename` truncates to 120 chars and falls back to `"output"`
- A malicious user can create many uploads with the same final name. Not a security issue per se, but combined with `make_job_dir` collision behaviour (`exist_ok=True`) it can lead to file overwrite within the same job dir. Verified safe: `make_job_dir` always creates a fresh `uuid4()` parent.

### L6 — No explicit cookie / session security headers
- The app sets only `Cache-Control: no-store` on `/`. No `X-Content-Type-Options: nosniff`, no `X-Frame-Options: DENY` (clickjacking protection), no `Referrer-Policy: no-referrer`. Adding these is a one-line middleware change.

### L7 — `/openapi.json` exposes the full API surface when `HT_PROFILE=dev`
- Already gated correctly via `docs_url`/`redoc_url`. In `prod`, the /openapi.json field is `None` so the route isn't registered. **Verified clean.**

### L8 — `extract_images` writes to `out_dir` from PDF — no per-image size cap
- A PDF with one 100 MB embedded image extracts the whole thing to disk. Combined with M9, an attacker can amplify upload size. Cap at e.g. 50 MB per image.

### L9 — `pdf_to_csv`, `pdf_to_markdown` write all output to disk; no row count cap
- A scanned table with 1M rows could create a huge CSV. Reasonable to cap at 100k rows / 50 MB output.

### L10 — `core/clamav_daemon.py:_ensure_config` writes `clamd.conf` only if missing
- Operator-friendly, but if the file is corrupted on disk, app silently runs with broken config. Add a checksum/version line and warn if mismatched.

### L11 — Self-signed cert private key is `NoEncryption()`
- `core/network.py:101-104`. Fine for ephemeral local server. Just note the `cert/server.key` file lives on disk in plaintext — operators should know.

### L12 — `Jinja2Templates` initialised once; autoescape is on by default
- **Verified clean.** No `|safe` filter in `templates/index.html`, no `{% autoescape false %}`. Server-rendered values (`{{ scheme }}`, `{{ port }}`, `{{ max_mb }}`, `{{ lan_ip }}`) are all integers/short strings the server controls. No XSS via template injection.

### L13 — `mimetypes.add_type` calls happen before StaticFiles mount — race-free, but globally mutates process state
- Fine; just notable that import order matters.

---

## Things checked but found clean

- **Random sources:** No `import random` usage anywhere in the codebase. All token generation uses `secrets.token_urlsafe(32)` (`routers/admin.py:28`) and `uuid4()` (job tokens). **Clean.**
- **`hmac.compare_digest`** correctly used for the mobile-token comparison (`app.py:263`). **Clean.**
- **`pickle.loads` / `yaml.load` / `eval()` / `exec()`:** No matches in source code (only in test fixtures and JS regex). **Clean.**
- **`shell=True`:** No matches. All `subprocess.run` and `subprocess.Popen` use list-form arguments. **Clean.**
- **Subprocess command injection:** All subprocess invocations in `pdf_safety.py`, `core/clamav_*.py` use list-form with absolute paths or `sys.executable` (except M10). The clamd Popen is constructed from list-form with hardcoded args. **Mostly clean** (see M10 for `python` PATH resolution).
- **SQL injection:** `core/history_db.py` uses parameterised queries (`?` placeholders) everywhere. `routers/history.py` uses `(limit,)` bind variable. `DELETE FROM history` has no user input. **Clean.**
- **Jinja2 autoescape:** Default `autoescape=True` for `.html` files; no `|safe` filter; values rendered are server-controlled. **Clean.**
- **Token format:** uuid4 hex (`[a-f0-9]{32}`) — 128 bits of entropy, unguessable. `check_token` correctly enforces format. **Clean** modulo C4 (the validation order issue).
- **Mobile token entropy:** `secrets.token_urlsafe(32)` → 32 bytes ≈ 256 bits. **Clean.**
- **CSV writer in `pdf_to_csv`:** Delegates to `parsers.generic_table.GenericTableParser.to_csv` which uses `csv` module — no formula-injection mitigation (cells starting with `=` will be evaluated by Excel), but that's a downstream-app problem, low risk for a CSV download.
- **Symlink containment:** `assert_under_work` uses `Path.resolve()` which follows symlinks before comparison. **Clean.**
- **ZIP slip in archive extraction:** No runtime `ZipFile.extractall` — only build-time in `build_portable.py` and `scripts/setup_clamav.py` (operator-controlled, not user input). **Clean.**

---

## Recommended fix order

The order below favours reachability × impact. Anything an attacker can drive from a hostile web page (operator's browser is the trust boundary) goes first.

1. **C5** — Add `gate_pdf_safety` to every `/pdf/*` and `/pdf/edit/*` endpoint. One-line change × 30 routes; eliminates the largest unverified attack surface.
2. **C1** — Patch `url_to_pdf` to validate redirects via custom `HTTPRedirectHandler`. Same patch should cap response size (C3).
3. **M6** — Lock down xhtml2pdf's `link_callback` to refuse `file://` and external `http://`. Extract this into `core/converters.py:_pisa_link_callback`.
4. **C4** — Move `core.check_token(token)` to the very first line of every token-taking endpoint; harden `make_job_dir` to `assert_under_work` *before* `mkdir`.
5. **H8/H7** — Add CSRF protection to `/admin/*` mutating endpoints (in addition to local-only check). Also addresses the "hostile site spins up the operator's mobile token" scenario.
6. **H2** — Drop the `?key=` URL fallback; require `X-Mobile-Key` header. Migrate the mobile-onboarding flow to a one-time token paste page that stores the key in `localStorage`.
7. **H3** — Document the reverse-proxy gotcha or add `HT_LOOPBACK_BYPASS=false` setting.
8. **H4/L7** — Trim `/health` public payload; gate detailed stats behind auth.
9. **C3** — Cap `urlopen.read()` to 50 MB, `/pdf/from-html` body to 10 MB.
10. **M4** — Gate `DELETE /history` behind mobile token.
11. **M8** — Bounded thread pool for background workers; reject with 503 over capacity.
12. **M9** — Drop default `MAX_UPLOAD_MB` to 200; raise via env for big-PDF users.
13. **M13** — Cap `parse_int_list` range expansion to 100k.
14. **M10** — Replace `"python"` with `sys.executable` in pdfid invocation.
15. **C2 / M5 / M6** — Verify and document the bundled `freshclam.conf`, `openpyxl` defusedxml usage, and `xhtml2pdf` URL-handling assumptions. Move to "must verify" CI checks.
16. **L6** — Add baseline security headers middleware (`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`) — same place CSP will eventually land.
17. **H1** — Modernise self-signed cert generation (`datetime.now(timezone.utc)` + annual rotation).
18. **H6 / M12** — Resource caps on subprocess + `ProcessPoolExecutor` workers.

The fixes through item 6 close every cross-origin-reachable hole. Items 7–10 are the operational/audit hardening. 11+ are defense in depth.

---

## Summary table

| # | Severity | Category | Title |
|---|---|---|---|
| C1 | Critical | SSRF / network | `/pdf/from-url` redirect bypasses `_assert_public_url` |
| C2 | High–Critical (verify) | Crypto / supply chain | `freshclam` config — verify HTTPS-only mirrors |
| C3 | High | Resource exhaustion | No size cap on `url_to_pdf` / `from-html` body |
| C4 | High | Path traversal / DoS | `make_job_dir` runs before token validation |
| C5 | High | Input validation | 30+ `/pdf/*` endpoints skip `gate_pdf_safety` |
| H1 | Medium-High | Crypto | Self-signed cert deprecated APIs + 5-year expiry |
| H2 | High | AuthN | `?key=` URL token fallback leaks via logs/history/referer |
| H3 | Medium-High | AuthN | `is_local_request` ignores trusted-proxy chain |
| H4 | Medium-High | Info disclosure | `/health` reveals telemetry without auth |
| H5 | Medium | Info disclosure | Version exposed in `/health` |
| H6 | Medium-High | Resource exhaustion | `clamd` spawned without OS resource caps |
| H7 | Medium-High | CSRF | `/admin/clamav-update` reachable via cross-origin POST |
| H8 | High | CSRF | `/admin/enable-mobile` mintable cross-origin (token rotation DoS) |
| H9 | Medium-High | SSRF | `_assert_public_url` TOCTOU vs DNS rebinding |
| M1 | Medium | Path / unicode | `safe_filename` no NFKC normalisation |
| M2 | Medium | Input validation | `check_structure` 4 MB head/tail blind spot |
| M3 | Low-Medium | Concurrency | Single shared sqlite connection |
| M4 | Medium | AuthN | `DELETE /history` unauthenticated |
| M5 | Medium (verify) | Parser | openpyxl XXE — verify defusedxml |
| M6 | Medium-High (verify) | LFI | xhtml2pdf reads `file://` URLs in HTML |
| M7 | Low | SSRF | URL embeds basic-auth credentials |
| M8 | Medium | Resource exhaustion | Unbounded background thread spawning |
| M9 | Medium | Resource exhaustion | 2 GB default `MAX_UPLOAD_MB` is excessive |
| M10 | Medium | Subprocess | `pdfid.py` invoked via PATH-resolved `python` |
| M11 | Low | Side-channel | First-found font cache stickiness |
| M12 | Medium | Resource exhaustion | Process-pool workers have no resource caps |
| M13 | Medium | Resource exhaustion | `parse_int_list` expands huge ranges |
| M14 | Low | Hardening | Inline JS in `index.html` makes future CSP harder |
| L1–L13 | Low | Various | See sections above |
