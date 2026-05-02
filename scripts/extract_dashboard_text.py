"""Extract visible text phrases from the rendered dashboard HTML for Phase 20 audit.

Approach:
1. Strip <style>, <script>, <head> blocks.
2. Walk a minimal HTML tokenizer keeping track of the current `data-view` attribute
   so we can attribute each phrase to the right tab.
3. Emit one TSV row per unique text:  count<TAB>view<TAB>parent<TAB>text

Usage:
    python3 scripts/extract_dashboard_text.py reports/xauusd_dashboard.html
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path


TAG_RE = re.compile(r"<(/?)([a-zA-Z][\w-]*)([^>]*)>", re.DOTALL)
ATTR_RE = re.compile(r"""([\w:-]+)\s*=\s*"([^"]*)"|([\w:-]+)\s*=\s*'([^']*)'""")
SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}


def strip_blocks(text: str) -> str:
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<head[^>]*>.*?</head>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text


def extract(html_text: str):
    body = strip_blocks(html_text)
    pos = 0
    skip_depth = 0
    current_view = "global"
    view_stack: list[tuple[int, str]] = []
    parent_stack: list[str] = []
    records: list[tuple[str, str, str]] = []
    open_depth = 0

    for m in TAG_RE.finditer(body):
        chunk = body[pos:m.start()]
        if chunk and skip_depth == 0:
            text = html.unescape(chunk).strip()
            if len(text) >= 3:
                parent = parent_stack[-1] if parent_stack else ""
                records.append((current_view, parent, text))
        pos = m.end()
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3) or ""
        is_self_closing = attrs.rstrip().endswith("/")
        if closing:
            if tag in SKIP_TAGS and skip_depth > 0:
                skip_depth -= 1
            if parent_stack and parent_stack[-1] == tag:
                parent_stack.pop()
            open_depth -= 1
            if view_stack and view_stack[-1][0] >= open_depth:
                view_stack.pop()
                current_view = view_stack[-1][1] if view_stack else "global"
        else:
            if tag in SKIP_TAGS:
                skip_depth += 1
            if not is_self_closing and tag not in {"br", "img", "hr", "meta", "link", "input", "source"}:
                parent_stack.append(tag)
                open_depth += 1
                attr_map: dict[str, str] = {}
                for am in ATTR_RE.finditer(attrs):
                    k = am.group(1) or am.group(3)
                    v = am.group(2) or am.group(4)
                    attr_map[k.lower()] = v
                view_id = attr_map.get("data-view")
                if not view_id and attr_map.get("data-tab-target"):
                    view_id = attr_map.get("data-tab-target")
                if view_id:
                    current_view = view_id
                    view_stack.append((open_depth, view_id))

    return records


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: extract_dashboard_text.py <html_path>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    records = extract(text)

    seen: dict[tuple[str, str], tuple[str, int]] = {}
    for view, parent, phrase in records:
        key = (view, phrase)
        if key in seen:
            p, n = seen[key]
            seen[key] = (p, n + 1)
        else:
            seen[key] = (parent, 1)

    rows = [(v, t, p, n) for (v, t), (p, n) in seen.items()]
    rows.sort(key=lambda r: (r[0], -r[3], r[1]))
    for view, phrase, parent, count in rows:
        clean = phrase.replace("\t", " ").replace("\n", " ").strip()
        if not clean:
            continue
        print(f"{count}\t{view}\t{parent}\t{clean}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
