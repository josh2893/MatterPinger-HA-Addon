#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from typing import Any

import websocket


# -----------------------------------------------------------------------------
# Configuration helpers
# -----------------------------------------------------------------------------
def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(float(os.environ.get(name, str(default))))
    except Exception:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except Exception:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


WS_URL = env_str("WS_URL", "ws://core-matter-server:5580/ws")
MATCH = env_str("MATCH", "bilresa")
NODE_IDS_RAW = env_str("NODE_IDS", "")
INTERVAL_SECONDS = env_int("INTERVAL_SECONDS", 120)
PING_ATTEMPTS = env_int("PING_ATTEMPTS", 3)
DELAY_SECONDS = env_float("DELAY_SECONDS", 0.5)
LIST_ONLY = env_bool("LIST_ONLY", True)
NO_COLOR = env_bool("NO_COLOR", False)
PING_RETRY_LIMIT = env_int("PING_RETRY_LIMIT", 3)
PING_RETRY_DELAY_SECONDS = env_float("PING_RETRY_DELAY_SECONDS", 3.0)
VERIFY_INTERVIEW_DELAY_SECONDS = env_float("VERIFY_INTERVIEW_DELAY_SECONDS", 1.0)


# -----------------------------------------------------------------------------
# ANSI styling helpers
# -----------------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
GREY = "\033[90m"

SECTION_COLORS = {
    "STARTUP": CYAN,
    "CYCLE": BLUE,
    "CONNECTION": CYAN,
    "DISCOVERY": MAGENTA,
    "FILTER": BLUE,
    "TARGETS": GREEN,
    "ACTION": CYAN,
    "VERIFY": MAGENTA,
    "SLEEP": GREY,
    "CONFIG": YELLOW,
}

LEVEL_COLORS = {
    "INFO": CYAN,
    "WARN": YELLOW,
    "ERROR": RED,
}


def paint(text: str, *styles: str) -> str:
    if NO_COLOR or not styles:
        return text
    return "".join(styles) + text + RESET


def timestamp_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(section: str, message: str, level: str = "INFO") -> None:
    ts = paint(f"[{timestamp_text()}]", DIM)
    lvl = paint(f"[{level}]", BOLD, LEVEL_COLORS.get(level, WHITE))
    sec = paint(f"[{section}]", BOLD, SECTION_COLORS.get(section, WHITE))
    print(f"{ts} {lvl} {sec} {message}", flush=True)


def status_tag(text: str, color: str) -> str:
    return paint(text, BOLD, color)


def yes_no(value: Any) -> str:
    return status_tag("Yes", GREEN) if value else status_tag("No", RED)


# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------
HW_VERSION_RE = re.compile(r"^P\d+(?:\.\d+)+$", re.IGNORECASE)
FW_VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")
MODEL_RE = re.compile(r"^[A-Z]\d{3,5}$")
HEXISH_RE = re.compile(r"^[a-f0-9]{16,}$", re.IGNORECASE)
TOKENISH_RE = re.compile(r"^[A-Za-z0-9/_-]{20,}$")
ALLOWED_TEXT_RE = re.compile(r"^[A-Za-z0-9 .:/_-]+$")

NOISE_EXACT = {
    "primary battery",
    "aaa",
    "swift home",
    "reset the application",
    "rotary",
}

NOISE_SUBSTRINGS = (
    "google-",
    "xhmiwlbtc3q",
    "/db+",
    "/sa8",
    "/oaaa",
    "qp0gpg",
    "bi58",
    "ab//",
)

PRODUCT_KEYWORDS = (
    "bilresa",
    "timmerflotte",
    "dirigera",
    "rodret",
    "styrbar",
    "parasoll",
    "vallhorn",
    "vindstyrka",
    "somrig",
)

TYPE_KEYWORDS = (
    "scroll wheel",
    "temp/hmd sensor",
    "temperature sensor",
    "humidity sensor",
    "motion sensor",
    "contact sensor",
    "button",
    "sensor",
    "bridge",
    "remote",
    "switch",
    "hub",
)


def parse_node_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            log("CONFIG", f"Ignoring invalid node ID '{part}'", level="WARN")
    return ids


def log_startup(explicit_ids: list[int], match_terms: list[str]) -> None:
    log("STARTUP", "Matter Node Pinger starting")
    log("STARTUP", f"Matter Server URL       : {paint(WS_URL, BOLD)}")
    log("STARTUP", f"Explicit Node IDs       : {paint(str(explicit_ids), BOLD) if explicit_ids else 'None'}")
    log("STARTUP", f"Match Terms             : {paint(str(match_terms), BOLD) if match_terms else 'None'}")
    log("STARTUP", f"Interval                : {INTERVAL_SECONDS} seconds")
    log("STARTUP", f"Ping Attempts           : {PING_ATTEMPTS}")
    log("STARTUP", f"Ping Retry Limit        : {PING_RETRY_LIMIT} total attempt(s)")
    log("STARTUP", f"Ping Retry Delay        : {PING_RETRY_DELAY_SECONDS} seconds")
    log("STARTUP", f"Ping to Interview Delay : {DELAY_SECONDS} seconds")
    log("STARTUP", f"Verify Interview Delay  : {VERIFY_INTERVIEW_DELAY_SECONDS} seconds")
    log("STARTUP", f"List Only Mode          : {yes_no(LIST_ONLY)}")
    log("STARTUP", f"ANSI Colours Enabled    : {yes_no(not NO_COLOR)}")


def short_json(obj: Any, limit: int = 240) -> str:
    text = json.dumps(obj, ensure_ascii=False)
    return text[:limit] + ("..." if len(text) > limit else "")


def node_id_of(node: dict) -> int | None:
    value = node.get("node_id")
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return None


def last_interview_of(node: dict | None) -> str | None:
    if not isinstance(node, dict):
        return None
    value = node.get("last_interview")
    return value if isinstance(value, str) and value.strip() else None


def collect_string_values(obj: Any) -> list[str]:
    results: list[str] = []

    if isinstance(obj, dict):
        for value in obj.values():
            results.extend(collect_string_values(value))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(collect_string_values(item))
    elif isinstance(obj, str):
        value = " ".join(obj.split()).strip()
        if value:
            results.append(value)

    return results


def is_readable_identity_string(value: str) -> bool:
    s = " ".join(value.split()).strip()
    if not s:
        return False

    low = s.lower()

    if low in {"true", "false", "null", "none"}:
        return False
    if low in NOISE_EXACT:
        return False
    if any(noise in low for noise in NOISE_SUBSTRINGS):
        return False
    if low.startswith("www."):
        return False
    if low.startswith("fe80:") or low.startswith("fd"):
        return False
    if low.startswith("0x"):
        return False
    if len(low) >= 19 and low[0:4].isdigit() and "t" in low and ":" in low:
        return False
    if HEXISH_RE.fullmatch(s):
        return False
    if ("=" in s or "+" in s) and " " not in s:
        return False
    if s.startswith("/"):
        return False
    if TOKENISH_RE.fullmatch(s) and not (
        HW_VERSION_RE.fullmatch(s) or FW_VERSION_RE.fullmatch(s) or MODEL_RE.fullmatch(s)
    ):
        return False
    if len(s) > 40 and " " not in s:
        return False
    if not ALLOWED_TEXT_RE.fullmatch(s):
        return False
    if "/" in s and " " not in s and not any(k in low for k in TYPE_KEYWORDS):
        return False

    return True


def unique_preserve(strings: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for s in strings:
        cleaned = " ".join(str(s).split()).strip()
        if not cleaned:
            continue
        low = cleaned.lower()
        if low in seen:
            continue
        seen.add(low)
        output.append(cleaned)
    return output


def identity_strings(node: dict) -> list[str]:
    raw = collect_string_values(node)
    readable = [s for s in raw if is_readable_identity_string(s)]
    return unique_preserve(readable)


def first_match(strings: list[str], predicate) -> str | None:
    for s in strings:
        if predicate(s):
            return s
    return None


def classify_identity(strings: list[str]) -> dict[str, str | None]:
    vendor = first_match(strings, lambda s: "ikea of sweden" in s.lower())
    if vendor is None:
        vendor = first_match(strings, lambda s: s.lower() == "ikea")

    product = first_match(strings, lambda s: any(word in s.lower() for word in PRODUCT_KEYWORDS))

    device_type = first_match(
        strings,
        lambda s: any(word in s.lower() for word in TYPE_KEYWORDS) and s.lower() != (product or "").lower(),
    )

    hw_version = first_match(strings, lambda s: bool(HW_VERSION_RE.fullmatch(s)))
    fw_version = first_match(strings, lambda s: bool(FW_VERSION_RE.fullmatch(s)))
    model = first_match(strings, lambda s: bool(MODEL_RE.fullmatch(s)))

    return {
        "vendor": vendor,
        "product": product,
        "device_type": device_type,
        "hardware_version": hw_version,
        "firmware_version": fw_version,
        "model": model,
    }


def node_summary_parts(node: dict) -> list[str]:
    strings = identity_strings(node)
    fields = classify_identity(strings)

    parts: list[str] = []
    for key in ("vendor", "product", "device_type", "hardware_version", "firmware_version", "model"):
        value = fields.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    if not parts:
        fallback = [s for s in strings if len(s) <= 40][:6]
        return unique_preserve(fallback)

    return unique_preserve(parts)


def friendly_name(node: dict) -> str:
    parts = node_summary_parts(node)
    return " | ".join(parts) if parts else short_json(node, 160)


def compact_match_basis(node: dict) -> str:
    return " | ".join(node_summary_parts(node)).lower()


def describe_selection_mode(explicit_ids: list[int], match_terms: list[str]) -> str:
    if explicit_ids:
        return f"explicit node IDs {explicit_ids}"
    if match_terms:
        return f"match terms {match_terms}"
    return "no selection criteria"


def match_terms_hit(match_basis: str, match_terms: list[str]) -> list[str]:
    lowered_basis = match_basis.lower()
    hits: list[str] = []
    for term in match_terms:
        clean = term.strip().lower()
        if clean and clean in lowered_basis:
            hits.append(term)
    return hits


def selection_status(node: dict, explicit_ids: list[int], match_terms: list[str]) -> tuple[bool, str]:
    nid = node_id_of(node)
    is_bridge = bool(node.get("is_bridge", False))
    basis = compact_match_basis(node)

    if explicit_ids:
        if nid in explicit_ids:
            return True, f"selected by explicit node ID list {explicit_ids}"
        return False, f"not in explicit node ID list {explicit_ids}"

    if not match_terms:
        return False, "no explicit node IDs or match terms configured"

    if is_bridge:
        return False, "bridge node ignored by text matching"

    hits = match_terms_hit(basis, match_terms)
    if hits:
        return True, f"matched filter term(s) {hits} against '{basis}'"
    return False, f"did not match filter term(s) {match_terms} against '{basis}'"


def human_interview_result(result: Any) -> str:
    if result is None:
        return f"{status_tag('Completed', GREEN)} (no response details returned)"
    return paint(short_json(result, 500), BOLD)


def format_timestamp_or_unknown(value: str | None) -> str:
    return value if value else paint("Unknown", BOLD, YELLOW)


# -----------------------------------------------------------------------------
# Matter WebSocket client
# -----------------------------------------------------------------------------
class MatterWsClient:
    def __init__(self, uri: str, timeout: int = 20) -> None:
        self.uri = uri
        self.timeout = timeout
        self.ws: websocket.WebSocket | None = None

    def connect(self) -> None:
        self.ws = websocket.create_connection(self.uri, timeout=self.timeout)
        try:
            hello = json.loads(self.ws.recv())
            log("CONNECTION", f"Connected to Matter Server at {paint(self.uri, BOLD)}")
            sdk_version = hello.get("sdk_version") if isinstance(hello, dict) else None
            if sdk_version:
                log("CONNECTION", f"Server Version          : {sdk_version}")
            schema_version = hello.get("schema_version") if isinstance(hello, dict) else None
            if schema_version is not None:
                log("CONNECTION", f"Schema Version          : {schema_version}")
        except Exception:
            log("CONNECTION", f"Connected to Matter Server at {paint(self.uri, BOLD)}")

    def close(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None

    def command(self, command: str, args: dict | None = None, timeout: int | None = None) -> Any:
        if self.ws is None:
            raise RuntimeError("WebSocket is not connected")

        message_id = str(uuid.uuid4())
        payload = {
            "message_id": message_id,
            "command": command,
            "args": args or {},
        }
        self.ws.send(json.dumps(payload))

        end_time = time.time() + (timeout or self.timeout)

        while time.time() < end_time:
            raw = self.ws.recv()
            msg = json.loads(raw)

            if msg.get("message_id") != message_id:
                continue

            if "error_code" in msg:
                raise RuntimeError(
                    f"{command} failed: error_code={msg.get('error_code')} details={msg.get('details')}"
                )

            return msg.get("result")

        raise TimeoutError(f"Timed out waiting for {command}")


# -----------------------------------------------------------------------------
# Discovery / selection / actions
# -----------------------------------------------------------------------------
def extract_nodes(result: Any) -> list[dict]:
    if isinstance(result, list):
        return [x for x in result if isinstance(x, dict)]

    if isinstance(result, dict):
        if isinstance(result.get("nodes"), list):
            return [x for x in result["nodes"] if isinstance(x, dict)]

        values = [v for v in result.values() if isinstance(v, dict)]
        if values:
            return values

    raise RuntimeError(f"Unexpected get_nodes response: {type(result).__name__}")


def get_nodes(client: MatterWsClient) -> list[dict]:
    return extract_nodes(client.command("get_nodes", {}, timeout=30))


def get_node_by_id(client: MatterWsClient, node_id: int) -> dict | None:
    nodes = get_nodes(client)
    for node in nodes:
        if node_id_of(node) == node_id:
            return node
    return None


def discover_nodes(client: MatterWsClient, explicit_ids: list[int], match_terms: list[str]) -> list[dict]:
    nodes = get_nodes(client)

    bridge_count = sum(1 for node in nodes if node.get("is_bridge", False))
    end_device_count = len(nodes) - bridge_count

    log(
        "DISCOVERY",
        f"Discovered {paint(str(len(nodes)), BOLD)} commissioned node(s): "
        f"{paint(str(end_device_count), BOLD)} end device(s), {paint(str(bridge_count), BOLD)} bridge(s)",
    )

    for node in nodes:
        if node.get("is_bridge", False):
            continue

        nid = node_id_of(node)
        available = bool(node.get("available"))
        name = friendly_name(node)
        basis = compact_match_basis(node)
        matched, reason = selection_status(node, explicit_ids, match_terms)

        log("DISCOVERY", f"Node {paint(str(nid), BOLD)}: {paint(name, BOLD)}")
        log("DISCOVERY", f"Node {nid}: Available={yes_no(available)} | Match Basis='{basis}'")

        if explicit_ids or match_terms:
            if matched:
                log("FILTER", f"Node {nid}: {status_tag('MATCHED', GREEN)} — {reason}")
            else:
                log("FILTER", f"Node {nid}: {status_tag('NOT MATCHED', YELLOW)} — {reason}")

    if bridge_count:
        log(
            "DISCOVERY",
            "Bridge nodes were omitted from detailed logs and will be ignored by text matching",
        )

    return nodes


def select_target_ids(nodes: list[dict], explicit_ids: list[int], match_terms: list[str]) -> list[int]:
    selected: list[int] = []

    for node in nodes:
        matched, _ = selection_status(node, explicit_ids, match_terms)
        nid = node_id_of(node)
        if matched and nid is not None:
            selected.append(nid)

    if explicit_ids:
        existing = {node_id_of(n) for n in nodes}
        missing = [nid for nid in explicit_ids if nid not in existing]
        for nid in missing:
            log("TARGETS", f"Configured node ID {nid} is not currently present in get_nodes", level="WARN")

    return selected


def ping_with_retry(client: MatterWsClient, node_id: int) -> Any:
    total_attempts = max(1, PING_RETRY_LIMIT)

    for attempt in range(1, total_attempts + 1):
        log(
            "ACTION",
            f"Node {paint(str(node_id), BOLD)}: {status_tag('PING', CYAN)} attempt {paint(str(attempt), BOLD)} of {paint(str(total_attempts), BOLD)} starting",
        )

        try:
            ping_result = client.command(
                "ping_node",
                {"node_id": node_id, "attempts": PING_ATTEMPTS},
                timeout=45,
            )
            log("ACTION", f"Node {node_id}: Ping Result       = {paint(short_json(ping_result), BOLD)}")

            if attempt > 1:
                log(
                    "ACTION",
                    f"Node {node_id}: {status_tag('RECOVERED', GREEN)} — ping succeeded on retry attempt {attempt}",
                )

            return ping_result

        except Exception as err:
            if attempt < total_attempts:
                log(
                    "ACTION",
                    f"Node {node_id}: {status_tag('PING FAILED', YELLOW)} — attempt {attempt} of {total_attempts} failed: {err}",
                    level="WARN",
                )
                log(
                    "ACTION",
                    f"Node {node_id}: waiting {PING_RETRY_DELAY_SECONDS} seconds before retrying ping",
                    level="WARN",
                )
                time.sleep(PING_RETRY_DELAY_SECONDS)
            else:
                raise RuntimeError(
                    f"Ping failed after {total_attempts} attempt(s): {err}"
                ) from err

    raise RuntimeError("Ping failed for an unknown reason")


def verify_interview(client: MatterWsClient, node_id: int, before_timestamp: str | None) -> None:
    time.sleep(VERIFY_INTERVIEW_DELAY_SECONDS)
    node_after = get_node_by_id(client, node_id)
    after_timestamp = last_interview_of(node_after)
    advanced = bool(before_timestamp and after_timestamp and after_timestamp != before_timestamp)

    log("VERIFY", f"Node {node_id}: Last Interview Before = {paint(format_timestamp_or_unknown(before_timestamp), BOLD)}")
    log("VERIFY", f"Node {node_id}: Last Interview After  = {paint(format_timestamp_or_unknown(after_timestamp), BOLD)}")

    if advanced:
        log("VERIFY", f"Node {node_id}: {status_tag('Interview Verified', GREEN)} — interview timestamp advanced")
    else:
        if before_timestamp is None and after_timestamp:
            log(
                "VERIFY",
                f"Node {node_id}: {status_tag('Partially Verified', YELLOW)} — post interview timestamp is available but there was no earlier value to compare",
                level="WARN",
            )
        elif after_timestamp == before_timestamp:
            log(
                "VERIFY",
                f"Node {node_id}: {status_tag('Not Verified', YELLOW)} — interview completed but the timestamp did not change",
                level="WARN",
            )
        else:
            log(
                "VERIFY",
                f"Node {node_id}: {status_tag('Not Verified', YELLOW)} — could not confirm interview progress from the current node data",
                level="WARN",
            )


def ping_and_interview(client: MatterWsClient, node_id: int) -> None:
    node_before = get_node_by_id(client, node_id)
    before_timestamp = last_interview_of(node_before)

    ping_with_retry(client, node_id)

    time.sleep(DELAY_SECONDS)

    log("ACTION", f"Node {paint(str(node_id), BOLD)}: {status_tag('INTERVIEW', MAGENTA)} starting")
    interview_result = client.command(
        "interview_node",
        {"node_id": node_id},
        timeout=120,
    )
    log("ACTION", f"Node {node_id}: Interview Result  = {human_interview_result(interview_result)}")

    verify_interview(client, node_id, before_timestamp)

    log(
        "ACTION",
        f"Node {node_id}: {status_tag('COMPLETE', GREEN)} — ping, interview, and verification steps finished",
    )


def main() -> int:
    explicit_ids = parse_node_ids(NODE_IDS_RAW)
    match_terms = [x.strip() for x in MATCH.split(",") if x.strip()]

    log_startup(explicit_ids, match_terms)

    cycle = 0

    while True:
        cycle += 1
        client = MatterWsClient(WS_URL, timeout=20)

        log("CYCLE", f"Starting cycle {paint(str(cycle), BOLD)} using {describe_selection_mode(explicit_ids, match_terms)}")

        try:
            client.connect()
            nodes = discover_nodes(client, explicit_ids, match_terms)

            if LIST_ONLY:
                log("TARGETS", "List Only Mode is enabled, so no nodes will be pinged or interviewed")
            else:
                targets = select_target_ids(nodes, explicit_ids, match_terms)

                if not targets:
                    log("TARGETS", "No target nodes were selected this cycle", level="WARN")
                else:
                    log("TARGETS", f"Selected Target Node IDs: {paint(str(targets), BOLD, GREEN)}")
                    for node_id in targets:
                        try:
                            ping_and_interview(client, node_id)
                        except Exception as err:
                            log("ACTION", f"Node {node_id}: {status_tag('FAILED', RED)} — {err}", level="ERROR")

        except Exception as err:
            log("CYCLE", f"Cycle {cycle} failed — {err}", level="ERROR")

        finally:
            client.close()

        log("SLEEP", f"Cycle {cycle} complete. Sleeping for {INTERVAL_SECONDS} seconds")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
