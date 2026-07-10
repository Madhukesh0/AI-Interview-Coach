# -*- coding: utf-8 -*-
"""
agent.py - watsonx Orchestrate streaming chat client.

Sends a user message to the agent and parses the Server-Sent Events (SSE)
stream to return the final assistant text.
"""

import json
import os
import uuid
from typing import Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

INSTANCE_URL   = os.getenv("INSTANCE_URL",   "")
AGENT_ID       = os.getenv("AGENT_ID",       "")
ENVIRONMENT_ID = os.getenv("ENVIRONMENT_ID", "")

_RUNS_ENDPOINT = (
    "{base}/v1/orchestrate/runs"
    "?stream=true&stream_timeout=120000&multiple_content=true"
)


def _build_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "text/event-stream",
    }


def _split_json_objects(text: str):
    """
    Split a string that contains one or more concatenated JSON objects
    e.g.  '{"a":1}{"b":2}{"c":3}'  ->  [{'a':1}, {'b':2}, {'c':3}]

    Uses json.JSONDecoder.raw_decode to walk through the string without
    requiring separators between objects.
    """
    decoder = json.JSONDecoder()
    pos = 0
    text = text.strip()
    objects = []
    while pos < len(text):
        # Skip whitespace between objects
        while pos < len(text) and text[pos] in ' \t\r\n':
            pos += 1
        if pos >= len(text):
            break
        try:
            obj, end_pos = decoder.raw_decode(text, pos)
            objects.append(obj)
            pos = end_pos
        except json.JSONDecodeError:
            # Skip one character and try again
            pos += 1
    return objects


def _parse_sse_events(raw: str):
    """
    Parse a raw SSE body into a list of (event_type, data_obj) tuples.

    Handles three formats watsonx Orchestrate may send:
    1. Concatenated JSON objects (no separator):
           {"id":…,"event":"run.started","data":{…}}{"id":…,"event":"message.completed","data":{…}}
    2. Newline-delimited JSON objects (one per line):
           {"id":…,"event":"message.completed","data":{…}}
    3. Classic multi-line SSE:
           event: message.completed
           data: {...}
    """
    events = []

    # ── Try splitting the whole raw body as concatenated JSON objects ────
    all_objects = _split_json_objects(raw)
    for obj in all_objects:
        if isinstance(obj, dict) and "event" in obj and "data" in obj:
            events.append((obj["event"], obj["data"]))

    if events:
        return events

    # ── Fallback: classic multi-line SSE format ──────────────────────────
    current_event = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            current_event = None
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload in ("", "[DONE]"):
                continue
            try:
                obj = json.loads(payload)
                events.append((current_event or "data", obj))
            except json.JSONDecodeError:
                pass

    return events


def _collect_content_list(content_list: list) -> str:
    """Extract text from a content array of {response_type/type, text} dicts."""
    parts = []
    for item in content_list:
        if isinstance(item, dict):
            # watsonx Orchestrate uses response_type; OpenAI-style uses type
            rt = item.get("response_type") or item.get("type", "")
            if rt == "text":
                parts.append(item.get("text", ""))
            elif "text" in item:
                parts.append(item["text"])
    return "".join(parts)


def _extract_text_from_stream(raw: str) -> str:
    """
    Return the final assistant reply text from the SSE stream.

    watsonx Orchestrate streams token-by-token via  message.delta  events
    and finishes with a  message.completed  event.  Both carry:
        data.delta.content  (list of {response_type:"text", text:"…"})

    Priority order:
    1. message.completed -> data.content  list
    2. message.completed -> data.output / data.text  (string fallback)
    3. message.delta     -> accumulated data.delta.content  tokens
    4. run.step.delta    -> delta.content  (older format)
    5. Any event         -> data.output / data.text  (last resort)
    """
    events = _parse_sse_events(raw)
    msg_delta_parts: list[str] = []
    completed_text = ""

    for event_type, data in events:

        # ── 1 & 2: fully-completed message ───────────────────────────────
        if event_type == "message.completed":
            content_list = data.get("content", [])
            if isinstance(content_list, list):
                completed_text = _collect_content_list(content_list)
            if not completed_text and isinstance(data.get("output"), str):
                completed_text = data["output"].strip()
            if not completed_text and isinstance(data.get("text"), str):
                completed_text = data["text"].strip()

        # ── 3: token-by-token streaming (primary path for this agent) ────
        elif event_type == "message.delta":
            delta = data.get("delta", {})
            content_list = delta.get("content", []) if isinstance(delta, dict) else []
            if isinstance(content_list, list):
                msg_delta_parts.append(_collect_content_list(content_list))

        # ── 4: run.step.delta (tool calls / older format) ─────────────────
        elif event_type == "run.step.delta":
            delta = data.get("delta", {})
            if isinstance(delta, dict):
                c = delta.get("content", "")
                if isinstance(c, str) and c:
                    msg_delta_parts.append(c)
                elif isinstance(c, list):
                    msg_delta_parts.append(_collect_content_list(c))

        # ── 5: generic fallback ───────────────────────────────────────────
        if not completed_text and not msg_delta_parts:
            for key in ("output", "text"):
                v = data.get(key, "")
                if isinstance(v, str) and v:
                    completed_text = v.strip()
                    break

    # message.completed is authoritative; fall back to accumulated deltas
    if completed_text:
        return completed_text
    joined = "".join(msg_delta_parts).strip()
    if joined:
        return joined
    return ""


def _extract_thread_id(raw: str, fallback: str) -> str:
    """
    Pull the thread_id out of any SSE event.
    Returns *fallback* if none is found.
    """
    for event_type, data in _parse_sse_events(raw):
        tid = (
            data.get("thread_id")
            or data.get("threadId")
            or (data.get("metadata") or {}).get("thread_id")
        )
        if tid:
            return tid
    return fallback


def chat_with_agent(
    user_message: str,
    token: str,
    thread_id: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Send *user_message* to the watsonx Orchestrate agent and return
    ``(assistant_reply, thread_id)``.

    Parameters
    ----------
    user_message : str
        The message to send.
    token : str
        A valid IBM Cloud IAM Bearer token (no "Bearer" prefix needed here).
    thread_id : Optional[str]
        Pass an existing thread_id to continue the same conversation.
        ``None`` starts a new thread.

    Returns
    -------
    tuple[str, str]
        ``(reply_text, thread_id)`` – thread_id may be a newly generated
        UUID if the server did not return one.
    """
    url = _RUNS_ENDPOINT.format(base=INSTANCE_URL.rstrip("/"))

    payload: dict = {
        "message": {
            "role":    "user",
            "content": user_message,
        },
        "agent_id":       AGENT_ID,
        "environment_id": ENVIRONMENT_ID,
    }

    # Include thread_id to maintain conversation history when provided
    if thread_id:
        payload["thread_id"] = thread_id

    resp = requests.post(
        url,
        headers=_build_headers(token),
        json=payload,
        stream=True,
        timeout=130,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Agent request failed [{resp.status_code}]: {resp.text[:500]}"
        )

    raw = resp.content.decode("utf-8", errors="replace")

    # Write raw SSE to a debug file so we can inspect the exact structure
    _debug_log = os.path.join(os.path.dirname(__file__), "last_sse_response.txt")
    try:
        with open(_debug_log, "w", encoding="utf-8") as _f:
            _f.write(raw)
    except OSError:
        pass

    reply        = _extract_text_from_stream(raw)
    returned_tid = _extract_thread_id(raw, fallback=thread_id or str(uuid.uuid4()))

    if not reply:
        # Last-ditch fallback: return the raw body so the user sees something
        reply = raw[:2000] if raw.strip() else "⚠️ Empty response from agent."

    return reply, returned_tid
