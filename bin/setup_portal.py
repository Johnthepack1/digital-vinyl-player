#!/usr/bin/env python3
import html
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime"
SETUP_MODE_FLAG = RUNTIME_DIR / "setup_mode.flag"


def load_env_file(path):
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


load_env_file(REPO_ROOT / ".env")

HOST = os.getenv("VINYL_SETUP_PORTAL_HOST", "127.0.0.1")
PORT = int(os.getenv("VINYL_SETUP_PORTAL_PORT", "8787"))
CAPTIVE_PORTAL_URL = os.getenv("VINYL_WIFI_LOGIN_URL", "http://neverssl.com/")
MUSIC_PROVIDER = os.getenv("VINYL_MUSIC_PROVIDER", "spotify").strip().lower()


def log(message):
    print(message, file=sys.stderr, flush=True)


def provider_name():
    if MUSIC_PROVIDER in ("apple", "applemusic", "apple_music"):
        return "Apple Music"
    return "Spotify"


def provider_login_url():
    if MUSIC_PROVIDER in ("apple", "applemusic", "apple_music"):
        return "https://music.apple.com/"
    return "https://accounts.spotify.com/en/login?continue=https%3A%2F%2Fopen.spotify.com%2F"


def run_command(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout or result.stderr or "").strip()
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 124, "Command timed out."
    except Exception as exc:
        return 1, str(exc)


def wifi_device_name():
    code, output = run_command(["nmcli", "-t", "-e", "no", "-f", "DEVICE,TYPE", "device", "status"])
    if code != 0:
        return None

    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "wifi":
            return parts[0]
    return None


def current_wifi_status():
    code, output = run_command(["nmcli", "-t", "-e", "no", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    if code != 0:
        return {"summary": output or "Could not query NetworkManager.", "connected": False}

    wifi_device = wifi_device_name()
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        device, dev_type, state, connection = parts[:4]
        if dev_type != "wifi":
            continue
        if wifi_device and device != wifi_device:
            continue

        connected = state == "connected" and connection not in ("--", "")
        if connected:
            return {"summary": f"Connected to {connection} on {device}.", "connected": True}
        return {"summary": f"{device} is {state}.", "connected": False}

    return {"summary": "No Wi-Fi adapter found.", "connected": False}


def scan_networks(rescan=False):
    cmd = ["nmcli", "-t", "-e", "no", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"]
    wifi_device = wifi_device_name()
    if wifi_device:
        cmd.extend(["ifname", wifi_device])
    cmd.extend(["--rescan", "yes" if rescan else "auto"])

    code, output = run_command(cmd)
    if code != 0:
        return [], output or "Could not scan Wi-Fi networks."

    deduped = {}
    for raw_line in output.splitlines():
        parts = raw_line.split(":")
        if len(parts) < 4:
            continue
        in_use, ssid, signal, security = parts[:4]
        ssid = ssid.strip()
        if not ssid:
            continue

        try:
            signal_value = int(signal)
        except ValueError:
            signal_value = 0

        entry = {
            "ssid": ssid,
            "signal": signal_value,
            "security": security or "Open",
            "active": in_use.strip() == "*",
        }
        existing = deduped.get(ssid)
        if existing is None or entry["active"] or signal_value > existing["signal"]:
            deduped[ssid] = entry

    networks = sorted(
        deduped.values(),
        key=lambda item: (not item["active"], -item["signal"], item["ssid"].lower()),
    )
    return networks, None


def connect_wifi(ssid, password, hidden=False):
    ssid = ssid.strip()
    if not ssid:
        return False, "SSID is required."

    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    wifi_device = wifi_device_name()
    if wifi_device:
        cmd.extend(["ifname", wifi_device])
    if password:
        cmd.extend(["password", password])
    if hidden:
        cmd.extend(["hidden", "yes"])

    code, output = run_command(cmd, timeout=60)
    if code == 0:
        return True, output or f"Connected to {ssid}."
    return False, output or f"Could not connect to {ssid}."


def disconnect_wifi():
    wifi_device = wifi_device_name()
    if not wifi_device:
        return False, "No Wi-Fi adapter found."

    code, output = run_command(["nmcli", "device", "disconnect", wifi_device], timeout=30)
    if code == 0:
        return True, output or f"Disconnected {wifi_device}."
    return False, output or f"Could not disconnect {wifi_device}."


def set_setup_mode(enabled):
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if enabled:
        SETUP_MODE_FLAG.write_text("1\n")
    elif SETUP_MODE_FLAG.exists():
        SETUP_MODE_FLAG.unlink()


def restart_spotify_service():
    code, output = run_command(["systemctl", "--user", "restart", "spotify.service"], timeout=30)
    return code == 0, output or "Restarted spotify.service."


def html_page(message="", error=""):
    status = current_wifi_status()
    networks, scan_error = scan_networks()

    message_html = f'<div class="banner ok">{html.escape(message)}</div>' if message else ""
    error_messages = [text for text in (error, scan_error) if text]
    error_html = "".join(
        f'<div class="banner error">{html.escape(text)}</div>' for text in error_messages
    )

    rows = []
    for network in networks:
        active_label = "Connected" if network["active"] else "Use"
        rows.append(
            """
            <tr>
              <td>{ssid}</td>
              <td>{signal}%</td>
              <td>{security}</td>
              <td>
                <button type="button" class="pick" data-ssid="{ssid_attr}">{active}</button>
              </td>
            </tr>
            """.format(
                ssid=html.escape(network["ssid"]),
                ssid_attr=html.escape(network["ssid"], quote=True),
                signal=network["signal"],
                security=html.escape(network["security"]),
                active=html.escape(active_label),
            )
        )

    network_rows = "\n".join(rows) or '<tr><td colspan="4">No visible Wi-Fi networks found.</td></tr>'
    provider = provider_name()
    provider_url = provider_login_url()

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Digital Vinyl Setup</title>
  <style>
    :root {{
      --bg: #f3efe6;
      --panel: rgba(255, 252, 245, 0.94);
      --ink: #1d1b18;
      --muted: #6d665d;
      --line: rgba(34, 31, 26, 0.12);
      --accent: #0f6c5c;
      --accent-2: #d66a2e;
      --error: #9c2f2f;
      --ok: #1e6b39;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "DejaVu Sans", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(214,106,46,0.20), transparent 28%),
        radial-gradient(circle at top right, rgba(15,108,92,0.18), transparent 24%),
        linear-gradient(160deg, #f5f1e8, #e7ddcd);
      min-height: 100vh;
    }}
    .page {{
      max-width: 920px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 24px;
      box-shadow: 0 18px 40px rgba(40, 26, 16, 0.10);
      backdrop-filter: blur(10px);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 2rem;
      line-height: 1.1;
    }}
    p {{
      margin: 0;
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.5;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
      margin-top: 20px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 20px;
      box-shadow: 0 12px 26px rgba(42, 29, 20, 0.08);
    }}
    .banner {{
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      font-weight: 600;
    }}
    .banner.ok {{
      background: rgba(30,107,57,0.11);
      color: var(--ok);
    }}
    .banner.error {{
      background: rgba(156,47,47,0.12);
      color: var(--error);
    }}
    .status {{
      margin-top: 14px;
      font-weight: 600;
      color: {"var(--ok)" if status["connected"] else "var(--accent-2)"};
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }}
    .button, button {{
      appearance: none;
      border: none;
      border-radius: 16px;
      background: var(--accent);
      color: white;
      padding: 14px 18px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
      text-align: center;
    }}
    .button.alt, button.alt {{
      background: var(--accent-2);
    }}
    .button.soft, button.soft {{
      background: rgba(29,27,24,0.08);
      color: var(--ink);
    }}
    form {{
      margin-top: 14px;
    }}
    label {{
      display: block;
      font-weight: 700;
      margin-top: 10px;
      margin-bottom: 6px;
    }}
    input[type="text"], input[type="password"] {{
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 14px 16px;
      font-size: 1rem;
      background: rgba(255,255,255,0.88);
    }}
    .hint {{
      margin-top: 8px;
      font-size: 0.95rem;
      color: var(--muted);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: middle;
    }}
    .pick {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(15,108,92,0.14);
      color: var(--accent);
    }}
    .footer {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <h1>Setup Mode</h1>
      <p>Connect Wi-Fi here, open a captive-portal login if needed, and use the other browser tab for {html.escape(provider)} sign-in. Hold the button again or tap Exit Setup when you are done.</p>
      <div class="status">{html.escape(status["summary"])}</div>
      {message_html}
      {error_html}
      <div class="actions">
        <a class="button" href="{html.escape(provider_url, quote=True)}" target="_blank" rel="noopener">Open {html.escape(provider)} Login</a>
        <a class="button alt" href="{html.escape(CAPTIVE_PORTAL_URL, quote=True)}" target="_blank" rel="noopener">Open Wi-Fi Login</a>
        <a class="button soft" href="/?rescan=1">Rescan Networks</a>
      </div>
    </section>

    <section class="grid">
      <article class="card">
        <h2>Join Wi-Fi</h2>
        <p>Pick a nearby network or type it manually. After connecting, tap Open Wi-Fi Login if your network uses a captive portal.</p>
        <form method="post" action="/connect">
          <label for="ssid">Wi-Fi name</label>
          <input id="ssid" name="ssid" type="text" autocomplete="off" required>
          <label for="password">Password</label>
          <input id="password" name="password" type="password" autocomplete="current-password">
          <label><input name="hidden" type="checkbox" value="1"> Hidden network</label>
          <div class="actions">
            <button type="submit">Connect</button>
            <button type="submit" class="soft" formaction="/disconnect" formmethod="post">Disconnect Wi-Fi</button>
          </div>
        </form>
        <div class="hint">The on-screen keyboard should appear when you tap a field.</div>
      </article>

      <article class="card">
        <h2>Nearby Networks</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Signal</th>
              <th>Security</th>
              <th>Use</th>
            </tr>
          </thead>
          <tbody>
            {network_rows}
          </tbody>
        </table>
      </article>
    </section>

    <section class="card">
      <h2>Return To Player</h2>
      <p>Exit setup mode and restart the music kiosk in normal player mode.</p>
      <form method="post" action="/exit-setup">
        <div class="actions">
          <button type="submit" class="alt">Exit Setup Mode</button>
        </div>
      </form>
      <div class="footer">Portal: http://{HOST}:{PORT}/</div>
    </section>
  </main>
  <script>
    for (const button of document.querySelectorAll('.pick')) {{
      button.addEventListener('click', () => {{
        document.getElementById('ssid').value = button.dataset.ssid;
        document.getElementById('password').focus();
      }});
    }}
  </script>
</body>
</html>
"""


class SetupPortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        message = query.get("message", [""])[0]
        error = query.get("error", [""])[0]
        rescan = query.get("rescan", ["0"])[0] == "1"

        if rescan:
            scan_networks(rescan=True)

        payload = html_page(message=message, error=error).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8")
        form = parse_qs(data)

        if self.path == "/connect":
            ssid = form.get("ssid", [""])[0]
            password = form.get("password", [""])[0]
            hidden = form.get("hidden", ["0"])[0] == "1"
            ok, message = connect_wifi(ssid, password, hidden=hidden)
            self.redirect(message=message if ok else "", error="" if ok else message)
            return

        if self.path == "/disconnect":
            ok, message = disconnect_wifi()
            self.redirect(message=message if ok else "", error="" if ok else message)
            return

        if self.path == "/exit-setup":
            set_setup_mode(False)
            restart_spotify_service()
            self.redirect(message="Exited setup mode. Reopening the player window.")
            return

        self.send_error(404)

    def log_message(self, format, *args):
        log("%s - %s" % (self.address_string(), format % args))

    def redirect(self, message="", error=""):
        location = "/"
        params = {}
        if message:
            params["message"] = message
        if error:
            params["error"] = error
        if params:
            location = location + "?" + urlencode(params)
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()


def main():
    server = ThreadingHTTPServer((HOST, PORT), SetupPortalHandler)
    log(f"Setup portal listening on http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
