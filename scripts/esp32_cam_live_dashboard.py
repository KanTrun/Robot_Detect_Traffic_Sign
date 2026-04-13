"""
Lightweight real-time dashboard for ESP32-CAM stream + serial metrics.

Run:
  python scripts/esp32_cam_live_dashboard.py \
    --serial-port COM7 \
    --stream-url http://192.168.4.1:81/stream
"""

import argparse
import json
import re
import threading
import time
from collections import deque

import serial
from flask import Flask, Response, jsonify, render_template_string, stream_with_context
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

SIGN_PATTERN = re.compile(r"^SIGN:(\d+):(\d+)\.(\d{2})$")
STATS_PATTERN_V2 = re.compile(r"^DBG:sent=(\d+) no_sign=(\d+) low_conf=(\d+) drop=(\d+) parse_fail=(\d+)$")
STATS_PATTERN_V1 = re.compile(r"^DBG:sent=(\d+) low_conf=(\d+) drop=(\d+) parse_fail=(\d+)$")
TOP_PATTERN = re.compile(
    r"^DBG:top=(\d+)\(([^)]*)\) conf=(\d+)\.(\d{2}) second=(\d+)\.(\d{2}) margin=(\d+)\.(\d{2})(?: stable=(\d+))?$"
)
NO_SIGN_PATTERN = re.compile(
    r"^DBG:no_sign top=(\d+) conf=(\d+)\.(\d{2}) second=(\d+)\.(\d{2}) margin=(\d+)\.(\d{2})$"
)
UNSTABLE_PATTERN = re.compile(
    r"^DBG:unstable top=(\d+) conf=(\d+)\.(\d{2}) margin=(\d+)\.(\d{2}) hits=(\d+)/(\d+)$"
)
STREAM_URL_PATTERN = re.compile(r"^DBG:stream_url=(https?://\S+)$")
STREAM_RECOVERED_PATTERN = re.compile(r"^DBG:stream_recovered url=(https?://\S+)$")


class RuntimeState:
    def __init__(self):
        self.lock = threading.Lock()
        self.started_at = time.time()
        self.connected = False
        self.reconnects = 0
        self.serial_errors = 0
        self.line_total = 0
        self.sign_total = 0
        self.unstable_total = 0
        self.class_counts = {}
        self.last_stats = {"sent": 0, "no_sign": 0, "low_conf": 0, "drop": 0, "parse_fail": 0}
        self.last_sign = None
        self.last_top = None
        self.last_no_sign = None
        self.fw_banner = ""
        self.last_line = ""
        self.last_line_ts = 0.0
        self.device_stream_url = ""
        self.recent_lines = deque(maxlen=50)
        self.update_seq = 0

    def _bump_update(self):
        self.update_seq += 1

    def set_connected(self, value: bool):
        with self.lock:
            self.connected = value
            self._bump_update()

    def mark_serial_error(self, reconnect: bool = False):
        with self.lock:
            self.serial_errors += 1
            if reconnect:
                self.reconnects += 1
            self.connected = False
            self._bump_update()

    def apply_line(self, line: str):
        now = time.time()
        with self.lock:
            self.line_total += 1
            self.last_line = line
            self.last_line_ts = now
            self.recent_lines.appendleft(line)

            if line.startswith("DBG:FW="):
                self.fw_banner = line

            m_sign = SIGN_PATTERN.match(line)
            if m_sign:
                cid = int(m_sign.group(1))
                conf = int(m_sign.group(2)) + int(m_sign.group(3)) / 100.0
                self.sign_total += 1
                self.class_counts[cid] = self.class_counts.get(cid, 0) + 1
                self.last_sign = {
                    "class_id": cid,
                    "conf": round(conf, 2),
                    "line": line,
                    "at": now,
                }

            m_stats = STATS_PATTERN_V2.match(line)
            if m_stats:
                self.last_stats = {
                    "sent": int(m_stats.group(1)),
                    "no_sign": int(m_stats.group(2)),
                    "low_conf": int(m_stats.group(3)),
                    "drop": int(m_stats.group(4)),
                    "parse_fail": int(m_stats.group(5)),
                }
            else:
                m_stats_old = STATS_PATTERN_V1.match(line)
                if m_stats_old:
                    self.last_stats = {
                        "sent": int(m_stats_old.group(1)),
                        "no_sign": 0,
                        "low_conf": int(m_stats_old.group(2)),
                        "drop": int(m_stats_old.group(3)),
                        "parse_fail": int(m_stats_old.group(4)),
                    }

            m_top = TOP_PATTERN.match(line)
            if m_top:
                self.last_top = {
                    "class_id": int(m_top.group(1)),
                    "label": m_top.group(2),
                    "conf": int(m_top.group(3)) + int(m_top.group(4)) / 100.0,
                    "second": int(m_top.group(5)) + int(m_top.group(6)) / 100.0,
                    "margin": int(m_top.group(7)) + int(m_top.group(8)) / 100.0,
                }

            m_stream = STREAM_URL_PATTERN.match(line)
            if m_stream:
                self.device_stream_url = m_stream.group(1)

            m_stream_recovered = STREAM_RECOVERED_PATTERN.match(line)
            if m_stream_recovered:
                self.device_stream_url = m_stream_recovered.group(1)

            m_no_sign = NO_SIGN_PATTERN.match(line)
            if m_no_sign:
                self.last_no_sign = {
                    "class_id": int(m_no_sign.group(1)),
                    "conf": int(m_no_sign.group(2)) + int(m_no_sign.group(3)) / 100.0,
                    "second": int(m_no_sign.group(4)) + int(m_no_sign.group(5)) / 100.0,
                    "margin": int(m_no_sign.group(6)) + int(m_no_sign.group(7)) / 100.0,
                }

            if UNSTABLE_PATTERN.match(line):
                self.unstable_total += 1

            self._bump_update()

    def snapshot(self):
        with self.lock:
            uptime = max(time.time() - self.started_at, 0.0)
            sign_per_min = self.sign_total / (uptime / 60.0) if uptime > 0 else 0.0
            return {
                "connected": self.connected,
                "reconnects": self.reconnects,
                "serial_errors": self.serial_errors,
                "uptime_sec": round(uptime, 1),
                "line_total": self.line_total,
                "sign_total": self.sign_total,
                "sign_per_min": round(sign_per_min, 3),
                "unstable_total": self.unstable_total,
                "last_stats": self.last_stats,
                "last_sign": self.last_sign,
                "last_top": self.last_top,
                "last_no_sign": self.last_no_sign,
                "class_counts": self.class_counts,
                "fw_banner": self.fw_banner,
                "last_line": self.last_line,
                "last_line_ts": self.last_line_ts,
                "device_stream_url": self.device_stream_url,
                "recent_lines": list(self.recent_lines),
                "update_seq": self.update_seq,
            }


def serial_worker(state: RuntimeState, port: str, baud: int, stop_event: threading.Event):
    ser = None
    while not stop_event.is_set():
        if ser is None:
            try:
                ser = serial.Serial(port, baudrate=baud, timeout=0.2)
                ser.setDTR(False)
                ser.setRTS(False)
                state.set_connected(True)
            except serial.SerialException:
                state.mark_serial_error()
                time.sleep(0.4)
                continue

        try:
            raw = ser.readline()
        except serial.SerialException:
            state.mark_serial_error(reconnect=True)
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(0.2)
            continue

        if not raw:
            continue

        line = raw.decode("utf-8", errors="ignore").strip()
        if line:
            state.apply_line(line)

    if ser is not None:
        try:
            ser.close()
        except Exception:
            pass


HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>ESP32-CAM Live Dashboard</title>
  <style>
    body{font-family:system-ui,Segoe UI,Arial;margin:12px;background:#111;color:#e8e8e8}
    .grid{display:grid;grid-template-columns:2fr 1fr;gap:12px}
    .card{background:#1a1a1a;border:1px solid #2b2b2b;border-radius:10px;padding:10px}
    .stream-container{position:relative}
    img{width:100%;height:auto;background:#000;border-radius:8px}
    .prediction-overlay{position:absolute;bottom:12px;left:12px;right:12px;background:rgba(0,0,0,0.75);backdrop-filter:blur(6px);border-radius:8px;padding:10px 14px;font-size:13px;display:none}
    .prediction-overlay.active{display:block}
    .pred-label{font-size:22px;font-weight:700;letter-spacing:0.5px}
    .pred-conf{font-size:14px;margin-top:2px}
    .conf-high{color:#4caf50}
    .conf-mid{color:#ff9800}
    .conf-low{color:#f44336}
    .kpi{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
    .kpi div{background:#151515;border:1px solid #2b2b2b;border-radius:8px;padding:8px}
    .muted{color:#9aa0a6;font-size:12px}
    .warn{color:#ffd166;font-size:12px;white-space:pre-wrap}
    pre{max-height:260px;overflow:auto;background:#0d0d0d;border:1px solid #2b2b2b;padding:8px;border-radius:8px}
    @media (max-width:900px){.grid{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <h3>ESP32-CAM Live Dashboard</h3>
  <div class=\"muted\">Stream URL (đang dùng): {{ stream_url }}</div>
  <div class=\"muted\">Fallback URL: {{ fallback_stream_url }}</div>
  <div class=\"muted\" style=\"margin-bottom:6px\">Proxy stream URL: {{ proxy_stream_url }}</div>
  <div id=\"stream_health\" class=\"warn\">{{ stream_warning }}</div>
  <div class=\"grid\">
    <div class=\"card\">
      <div class=\"stream-container\">
        <img id=\"stream\" alt=\"ESP32 stream\" style=\"display:block;margin:0 auto;width:min(100%,800px);max-height:75vh;height:auto;object-fit:contain;\" />
        <div id=\"pred_overlay\" class=\"prediction-overlay\">
          <div class=\"pred-label\" id=\"pred_label\">--</div>
          <div class=\"pred-conf\" id=\"pred_conf\">confidence: --</div>
        </div>
      </div>
    </div>
    <div class=\"card\">
      <div class=\"kpi\">
        <div><div class=\"muted\">sent</div><div id=\"sent\">0</div></div>
        <div><div class=\"muted\">no_sign</div><div id=\"no_sign\">0</div></div>
        <div><div class=\"muted\">low_conf</div><div id=\"low_conf\">0</div></div>
        <div><div class=\"muted\">drop</div><div id=\"drop\">0</div></div>
        <div><div class=\"muted\">parse_fail</div><div id=\"parse_fail\">0</div></div>
        <div><div class=\"muted\">sign/min</div><div id=\"sign_per_min\">0</div></div>
      </div>
      <hr style=\"border-color:#2b2b2b\" />
      <div id=\"status\" class=\"muted\">waiting...</div>
      <div class=\"muted\" id=\"last_top\"></div>
      <div class=\"muted\" id=\"last_sign\"></div>
      <div class=\"muted\" id=\"last_no_sign\"></div>
    </div>
  </div>
  <div class=\"card\" style=\"margin-top:12px\">
    <div class=\"muted\">Recent serial lines</div>
    <pre id=\"lines\"></pre>
  </div>

<script>
const ids = (id) => document.getElementById(id);
const evt = new EventSource('/events');
const streamUrl = {{ stream_url|tojson }};
const fallbackStreamUrl = {{ fallback_stream_url|tojson }};
const proxyStreamUrl = {{ proxy_stream_url|tojson }};
const captureProxyUrl = {{ capture_proxy_url|tojson }};

function render(d){
  ids('sent').textContent = d.last_stats.sent;
  ids('no_sign').textContent = d.last_stats.no_sign;
  ids('low_conf').textContent = d.last_stats.low_conf;
  ids('drop').textContent = d.last_stats.drop;
  ids('parse_fail').textContent = d.last_stats.parse_fail;
  ids('sign_per_min').textContent = d.sign_per_min;

  const nowSec = Date.now() / 1000;
  const serialAge = d.last_line_ts ? Math.max(0, nowSec - Number(d.last_line_ts)) : Number.POSITIVE_INFINITY;
  const serialFresh = Number.isFinite(serialAge) && serialAge <= 3.0;
  const serialState = serialFresh ? 'fresh' : `stale(${serialAge.toFixed(1)}s)`;

  let signFreshLabel = 'none';
  if (d.last_sign && d.last_sign.at) {
    const signAge = Math.max(0, nowSec - Number(d.last_sign.at));
    signFreshLabel = signAge <= 3.0 ? 'fresh' : `stale(${signAge.toFixed(1)}s)`;
  }

  ids('status').textContent = `connected=${d.connected} uptime=${d.uptime_sec}s lines=${d.line_total} unstable=${d.unstable_total} serial=${serialState}`;
  ids('last_top').textContent = d.last_top ? `top=${d.last_top.class_id}(${d.last_top.label}) conf=${d.last_top.conf} second=${d.last_top.second} margin=${d.last_top.margin}` : 'top=none';
  ids('last_sign').textContent = d.last_sign ? `last SIGN: class=${d.last_sign.class_id} conf=${d.last_sign.conf} (${signFreshLabel})` : 'last SIGN: none';
  ids('last_no_sign').textContent = d.last_no_sign ? `last no_sign: top=${d.last_no_sign.class_id} conf=${d.last_no_sign.conf} second=${d.last_no_sign.second} margin=${d.last_no_sign.margin}` : 'last no_sign: none';
  ids('lines').textContent = d.recent_lines.join('\\n');

  // Update prediction overlay
  const overlay = ids('pred_overlay');
  const predLabel = ids('pred_label');
  const predConf = ids('pred_conf');
  if (d.last_top && d.last_top.label) {
    const conf = d.last_top.conf;
    const label = d.last_top.label.replace(/_/g, ' ').toUpperCase();
    predLabel.textContent = `\\u{1F6A6} ${label}`;
    predConf.textContent = `confidence: ${(conf * 100).toFixed(0)}% | margin: ${(d.last_top.margin * 100).toFixed(0)}%`;
    predLabel.className = 'pred-label ' + (conf >= 0.9 ? 'conf-high' : conf >= 0.7 ? 'conf-mid' : 'conf-low');
    overlay.className = 'prediction-overlay active';
  } else {
    overlay.className = 'prediction-overlay';
  }
}

let lastEvtTs = 0;

evt.onmessage = (e) => {
  const data = JSON.parse(e.data);
  render(data);
  lastEvtTs = Date.now();
};

evt.onerror = () => {
  ids('status').textContent = 'event stream disconnected, retrying...';
};

async function pollSnapshot(){
  try {
    const resp = await fetch('/api/snapshot', { cache: 'no-store' });
    if (!resp.ok) {
      return;
    }
    const data = await resp.json();
    render(data);
  } catch (_) {
  }
}

setInterval(() => {
  if (Date.now() - lastEvtTs > 1200) {
    pollSnapshot();
  }
}, 1000);

pollSnapshot();

const streamImg = ids('stream');
const streamHealth = ids('stream_health');
let lastFrameTs = 0;
let frameWatchdogTimer = null;
let mjpegRetryTimer = null;
let captureTimer = null;
let captureAbortCtrl = null;
let streamMode = 'unknown';
let streamActiveUrl = streamUrl;
let streamSessionId = 0;
let lastSwitchTs = 0;
let fallbackCooldownUntil = 0;

function showStreamWarning(msg){
  if (msg && msg.trim() !== '') {
    streamHealth.textContent = msg;
  }
}

function clearStreamWarning(){
  streamHealth.textContent = '';
}

function ensureFrameWatchdog(){
  if (frameWatchdogTimer) {
    return;
  }
  frameWatchdogTimer = setInterval(() => {
    if (!lastFrameTs) {
      return;
    }
    const ageMs = Date.now() - lastFrameTs;
    if (ageMs > 3000) {
      showStreamWarning(`Stream có dấu hiệu stale (${(ageMs / 1000).toFixed(1)}s không có frame mới).`);
    }
  }, 1000);
}

function chooseStreamModeByUrl(url){
  return url.includes('/capture') ? 'capture' : 'mjpeg';
}

function stopCaptureMode(){
  if (captureTimer){
    clearTimeout(captureTimer);
    captureTimer = null;
  }
  if (captureAbortCtrl){
    captureAbortCtrl.abort();
    captureAbortCtrl = null;
  }
  const prevUrl = streamImg.dataset.objUrl;
  if (prevUrl) {
    URL.revokeObjectURL(prevUrl);
    delete streamImg.dataset.objUrl;
  }
}

function startCaptureMode(captureUrl){
  stopCaptureMode();
  streamMode = 'capture';

  const localSessionId = ++streamSessionId;
  const captureBaseUrl = captureProxyUrl;
  let busy = false;
  let delayMs = 300;

  const scheduleTick = () => {
    if (localSessionId !== streamSessionId || streamMode !== 'capture') {
      return;
    }
    captureTimer = setTimeout(tick, delayMs);
  };

  const tick = async () => {
    if (localSessionId !== streamSessionId || streamMode !== 'capture') {
      return;
    }

    if (busy) {
      scheduleTick();
      return;
    }

    busy = true;
    captureAbortCtrl = new AbortController();
    const timeoutId = setTimeout(() => {
      if (captureAbortCtrl) {
        captureAbortCtrl.abort();
      }
    }, 1500);

    try {
      const resp = await fetch(`${captureBaseUrl}?t=${Date.now()}`, {
        cache: 'no-store',
        signal: captureAbortCtrl.signal,
      });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const blob = await resp.blob();
      if (localSessionId !== streamSessionId || streamMode !== 'capture') {
        return;
      }
      const nextUrl = URL.createObjectURL(blob);
      const prevUrl = streamImg.dataset.objUrl;
      streamImg.src = nextUrl;
      streamImg.dataset.objUrl = nextUrl;
      if (prevUrl) {
        URL.revokeObjectURL(prevUrl);
      }
      clearStreamWarning();
      delayMs = 250;
    } catch (err) {
      showStreamWarning(`Capture lỗi/timed out (${captureBaseUrl}), dashboard đang retry...`);
      delayMs = Math.min(1200, delayMs + 180);
    } finally {
      clearTimeout(timeoutId);
      captureAbortCtrl = null;
      busy = false;
      scheduleTick();
    }
  };

  tick();
}

function startMjpegMode(mjpegUrl){
  stopCaptureMode();
  if (mjpegRetryTimer) {
    clearTimeout(mjpegRetryTimer);
    mjpegRetryTimer = null;
  }
  streamMode = 'mjpeg';
  streamSessionId += 1;
  const targetUrl = proxyStreamUrl || mjpegUrl;
  streamImg.src = `${targetUrl}${targetUrl.includes('?') ? '&' : '?'}t=${Date.now()}`;
}

function startStreamForUrl(url){
  streamActiveUrl = url;
  const mode = chooseStreamModeByUrl(url);
  if (mode === 'capture') {
    startCaptureMode(url);
  } else {
    startMjpegMode(url);
  }
}

function switchToOtherEndpoint(){
  const now = Date.now();
  if (now - lastSwitchTs < 1200) {
    return false;
  }

  if (!fallbackStreamUrl || fallbackStreamUrl === streamActiveUrl) {
    return false;
  }

  if (fallbackStreamUrl.includes('/capture') && now < fallbackCooldownUntil) {
    return false;
  }

  lastSwitchTs = now;
  if (fallbackStreamUrl.includes('/capture')) {
    fallbackCooldownUntil = now + 6000;
  }

  showStreamWarning(`Lỗi ${streamActiveUrl}, chuyển endpoint sang ${fallbackStreamUrl}`);
  startStreamForUrl(fallbackStreamUrl);
  return true;
}

startStreamForUrl(streamUrl);
ensureFrameWatchdog();

streamImg.addEventListener('load', () => {
  lastFrameTs = Date.now();
  if (streamMode !== 'capture') {
    fallbackCooldownUntil = Date.now() + 6000;
  }
  clearStreamWarning();
});

streamImg.addEventListener('error', () => {
  if (streamMode === 'capture') {
    showStreamWarning(`Capture lỗi tạm thời (${streamActiveUrl}), đang tự retry nội bộ qua proxy...`);
    return;
  }

  showStreamWarning('Stream /stream vừa ngắt, dashboard sẽ reconnect /stream. Không tự nhảy sang capture để tránh CORS/500.');
  if (mjpegRetryTimer) {
    clearTimeout(mjpegRetryTimer);
  }
  mjpegRetryTimer = setTimeout(() => {
    mjpegRetryTimer = null;
    startMjpegMode(streamUrl);
  }, 1200);
});
</script>
</body>
</html>
"""


def _replace_path(stream_url: str, new_path: str):
    parts = urlsplit(stream_url)
    path = new_path if new_path.startswith("/") else f"/{new_path}"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def build_stream_candidates(stream_url: str):
    parts = urlsplit(stream_url)
    path = parts.path or ""
    if path.endswith("/capture"):
        alt = _replace_path(stream_url, "/stream")
        return [stream_url, alt]
    if path.endswith("/stream"):
        alt = _replace_path(stream_url, "/capture")
        return [stream_url, alt]
    return [stream_url, _replace_path(stream_url, "/stream"), _replace_path(stream_url, "/capture")]


def check_stream_once(stream_url: str, timeout_sec: float = 6.0):
    req = Request(stream_url, method="GET")
    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            code = getattr(resp, "status", None)
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if code is not None and code >= 400:
                return False, code, f"HTTP {code}"
            if stream_url.rstrip("/").endswith("/stream"):
                if "multipart/x-mixed-replace" not in content_type:
                    return False, code, f"unexpected_content_type:{content_type or 'empty'}"
            elif stream_url.rstrip("/").endswith("/capture"):
                if "image/jpeg" not in content_type:
                    return False, code, f"unexpected_content_type:{content_type or 'empty'}"
            return True, code, ""
    except URLError as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, str(e)


def probe_stream_candidates(candidates):
    if not candidates:
        return "", None, "empty_candidates"

    first_fail_url = candidates[0]
    first_fail_code = None
    first_fail_err = ""

    for url in candidates:
        ok, code, err = check_stream_once(url)
        if ok:
            return url, code, ""
        if not first_fail_err:
            first_fail_url = url
            first_fail_code = code
            first_fail_err = err or (f"HTTP {code}" if code is not None else "unknown_error")

    return first_fail_url, first_fail_code, first_fail_err


def create_app(state: RuntimeState, stream_url: str):
    app = Flask(__name__)

    stream_state = {
        "configured_stream_url": stream_url,
        "primary_stream_url": stream_url,
        "fallback_stream_url": _replace_path(stream_url, "/capture"),
        "source_stream_url": _replace_path(stream_url, "/stream"),
        "source_capture_url": _replace_path(stream_url, "/capture"),
        "probe_code": None,
        "probe_err": "",
    }

    def recompute_sources(preferred_stream_url: str):
        candidates = build_stream_candidates(preferred_stream_url)
        probe_url, probe_code, probe_err = probe_stream_candidates(candidates)

        input_path = urlsplit(preferred_stream_url).path or ""
        if input_path.endswith("/stream"):
            primary_stream_url = preferred_stream_url
            fallback_stream_url = _replace_path(preferred_stream_url, "/capture")
        elif input_path.endswith("/capture"):
            primary_stream_url = preferred_stream_url
            fallback_stream_url = _replace_path(preferred_stream_url, "/stream")
        else:
            primary_stream_url = probe_url or preferred_stream_url
            fallback_stream_url = next((u for u in candidates if u != primary_stream_url), primary_stream_url)

        source_stream_url = primary_stream_url if primary_stream_url.rstrip("/").endswith("/stream") else _replace_path(preferred_stream_url, "/stream")
        source_capture_url = fallback_stream_url if fallback_stream_url.rstrip("/").endswith("/capture") else _replace_path(preferred_stream_url, "/capture")

        stream_state["primary_stream_url"] = primary_stream_url
        stream_state["fallback_stream_url"] = fallback_stream_url
        stream_state["source_stream_url"] = source_stream_url
        stream_state["source_capture_url"] = source_capture_url
        stream_state["probe_code"] = probe_code
        stream_state["probe_err"] = probe_err

    def refresh_stream_source_from_serial():
        snap = state.snapshot()
        device_stream_url = (snap.get("device_stream_url") or "").strip()
        if not device_stream_url:
            return
        if device_stream_url == stream_state["configured_stream_url"]:
            return
        stream_state["configured_stream_url"] = device_stream_url
        recompute_sources(device_stream_url)

    def fetch_capture_frame(timeout_sec: float = 3.0):
        refresh_stream_source_from_serial()
        source_capture_url = stream_state["source_capture_url"]
        source_stream_url = stream_state["source_stream_url"]

        capture_candidates = [source_capture_url, source_stream_url]

        for candidate in capture_candidates:
            req = Request(candidate, method="GET")
            try:
                with urlopen(req, timeout=timeout_sec) as resp:
                    code = getattr(resp, "status", 200) or 200
                    if code >= 400:
                        continue

                    content_type = (resp.headers.get("Content-Type") or "").lower()

                    if "image/jpeg" in content_type or candidate.rstrip("/").endswith("/capture"):
                        body = resp.read()
                        if body:
                            return body, "image/jpeg", code
                        continue

                    buffer = bytearray()
                    start_ts = time.time()
                    while time.time() - start_ts < timeout_sec:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        buffer.extend(chunk)

                        soi = buffer.find(b"\xff\xd8")
                        if soi == -1:
                            if len(buffer) > 65536:
                                del buffer[:-65536]
                            continue

                        eoi = buffer.find(b"\xff\xd9", soi + 2)
                        if eoi != -1:
                            frame = bytes(buffer[soi:eoi + 2])
                            if frame:
                                return frame, "image/jpeg", 200

                    continue
            except Exception:
                continue

        raise RuntimeError("capture_all_sources_failed")

    recompute_sources(stream_url)

    @app.get("/")
    def index():
        refresh_stream_source_from_serial()
        warning = ""

        primary_stream_url = stream_state["primary_stream_url"]
        fallback_stream_url = stream_state["fallback_stream_url"]
        probe_code = stream_state["probe_code"]
        probe_err = stream_state["probe_err"]
        configured_stream_url = stream_state["configured_stream_url"]

        stream_path = urlsplit(primary_stream_url).path or ""
        fallback_path = urlsplit(fallback_stream_url).path or ""

        if probe_err:
            warning = (
                "Probe ban đầu stream endpoint bị timeout/lỗi, dashboard vẫn sẽ tự thử lại ở client.\n"
                f"- URL gốc: {configured_stream_url}\n"
                f"- URL đang thử: {primary_stream_url}\n"
                f"- URL fallback: {fallback_stream_url}\n"
                "- Gợi ý: giữ tab mở 3-5 giây để auto-retry, tránh chỉ nhìn cảnh báo probe ban đầu.\n"
                f"- Chi tiết probe: {probe_err}"
            )
        elif stream_path.endswith("/stream") and not fallback_path.endswith("/capture"):
            warning = "Fallback URL chưa ở endpoint /capture, dashboard có thể fallback kém ổn định."
        elif stream_path.endswith("/capture") and not fallback_path.endswith("/stream"):
            warning = "Fallback URL chưa ở endpoint /stream, dashboard có thể fallback kém ổn định."
        elif probe_code is not None and probe_code >= 400:
            warning = f"Probe endpoint phản hồi HTTP {probe_code}, dashboard vẫn sẽ tự retry ở client."

        return render_template_string(
            HTML_TEMPLATE,
            stream_url=primary_stream_url,
            fallback_stream_url=fallback_stream_url,
            proxy_stream_url="/proxy/stream",
            capture_proxy_url="/proxy/capture",
            stream_warning=warning,
        )

    @app.get("/api/snapshot")
    def api_snapshot():
        refresh_stream_source_from_serial()
        return jsonify(state.snapshot())

    @app.get("/proxy/stream")
    def proxy_stream():
        boundary = "frame"

        def generate_chunks():
            while True:
                try:
                    body, content_type, _ = fetch_capture_frame(timeout_sec=3.0)
                    header = (
                        f"--{boundary}\r\n"
                        f"Content-Type: {content_type}\r\n"
                        f"Content-Length: {len(body)}\r\n\r\n"
                    ).encode("ascii")

                    yield header
                    yield body
                    yield b"\r\n"
                    time.sleep(0.06)
                except Exception:
                    time.sleep(0.25)
                    continue

        return Response(
            stream_with_context(generate_chunks()),
            mimetype=f"multipart/x-mixed-replace; boundary={boundary}",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/proxy/capture")
    def proxy_capture():
        try:
            body, content_type, code = fetch_capture_frame(timeout_sec=5.0)
            return Response(body, status=code, mimetype=content_type)
        except Exception:
            return Response(status=503)

    @app.get("/events")
    def events():
        def generate():
            last_seen = -1
            try:
                while True:
                    snap = state.snapshot()
                    if snap["update_seq"] != last_seen:
                        yield f"data: {json.dumps(snap, ensure_ascii=False)}\\n\\n"
                        last_seen = snap["update_seq"]
                    time.sleep(0.2)
            except GeneratorExit:
                return
            except Exception:
                return

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def main():
    parser = argparse.ArgumentParser(description="Live dashboard for ESP32-CAM stream + serial metrics")
    parser.add_argument("--serial-port", default="COM7")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--stream-url", default="http://192.168.1.226:81/stream")
    args = parser.parse_args()

    state = RuntimeState()
    stop_event = threading.Event()
    worker = threading.Thread(
        target=serial_worker,
        args=(state, args.serial_port, args.baud, stop_event),
        daemon=True,
    )
    worker.start()

    app = create_app(state, args.stream_url)
    print(f"[RUN] dashboard http://{args.host}:{args.port} stream={args.stream_url} serial={args.serial_port}@{args.baud}")
    try:
        app.run(host=args.host, port=args.port, debug=False, threaded=True, use_reloader=False)
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
