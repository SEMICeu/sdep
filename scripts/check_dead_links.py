#!/usr/bin/env python3
# Vendored from the check-dead-links skill so `make dod` works in every checkout.
# Reports relative links whose file or heading anchor does not exist.
"""Find dead links in Markdown files.

Scans every *.md under the given roots (default: the current directory) and
reports links that do not resolve: missing files, missing in-page anchors, and
optionally unreachable external URLs.

Anchors follow GitHub slug rules, including the -1, -2 suffixes GitHub adds to
duplicate headings. Anchors that only work on GitLab (which collapses repeated
hyphens, GitHub does not) are reported separately as renderer-dependent.

Usage:
  run.py                                  # scan ./**/*.md, internal links only
  run.py repo-a repo-b                    # scan several roots
  run.py --external                       # also probe http(s) URLs
  run.py --external --timeout 30
  run.py --exclude vendor --exclude tmp   # extra directories to skip
  run.py --include-images                 # also check ![](...) targets
  run.py --quiet                          # findings only, no OK lines

Exit codes: 0 = no dead links, 1 = dead links found, 2 = bad invocation.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse

DEFAULT_EXCLUDES = {
    ".git", ".hg", ".svn", ".tox", ".venv", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".next", ".nuxt", ".cache", "__pycache__", "node_modules",
    "venv", "site-packages", "dist", "build", "target", "htmlcov", "coverage",
}

# Inline links. The (?<!\!) guard drops images unless --include-images widens it.
INLINE = re.compile(r"(?<!\!)\[([^\]\n]*)\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")
IMAGE = re.compile(r"!\[([^\]\n]*)\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")
REFDEF = re.compile(r"^\s{0,3}\[([^\]^][^\]]*)\]:\s*(\S+)", re.M)
AUTOLINK = re.compile(r"<((?:https?|ftp)://[^>\s]+)>")
FENCE = re.compile(r"^(?P<f>```|~~~).*?^(?P=f)", re.S | re.M)
INLINE_CODE = re.compile(r"`+[^`\n]*`+")
ATX = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$", re.M)
HTML_H = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.I | re.S)
ANCHOR_ATTR = re.compile(r"(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", re.I)
UA = "Mozilla/5.0 (compatible; check-dead-links/1.0)"


def slug(text: str, squeeze: bool = False) -> str:
    """GitHub heading slug. squeeze=True gives the GitLab variant."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links keep their text
    text = re.sub(r"[`*_~]", "", text)
    text = unicodedata.normalize("NFKD", text).lower().strip()
    text = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
    return re.sub(r"-+", "-", text) if squeeze else text


def scrub(body: str) -> str:
    """Blank fenced blocks, keeping line numbers, so examples are not reported."""
    return FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), body)


def code_spans(text: str) -> list[tuple[int, int]]:
    """Offsets of inline code runs. A link is ignored only when it sits inside one,
    so a label like [API Layer (`app/api/`)] survives intact."""
    return [m.span() for m in INLINE_CODE.finditer(text)]


def anchors_of(path: Path, cache: dict) -> tuple[set, set]:
    if path in cache:
        return cache[path]
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        cache[path] = (set(), set())
        return cache[path]

    stripped = scrub(body)
    titles = [t for _, t in ATX.findall(stripped)] + [t for _, t in HTML_H.findall(stripped)]
    github, gitlab = set(), set()
    # Both renderers suffix repeated slugs with -1, -2, ... in document order.
    for seen, out, sq in ((Counter(), github, False), (Counter(), gitlab, True)):
        for title in titles:
            base = slug(title, squeeze=sq)
            n = seen[base]
            out.add(base if n == 0 else f"{base}-{n}")
            seen[base] += 1
    explicit = {a.lower() for a in ANCHOR_ATTR.findall(body)}
    github |= explicit
    gitlab |= explicit
    cache[path] = (github, gitlab)
    return cache[path]


def links_of(path: Path, include_images: bool) -> list[tuple[int, str, str]]:
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    text = scrub(body)
    spans = code_spans(text)
    patterns = [INLINE, REFDEF, AUTOLINK] + ([IMAGE] if include_images else [])
    found = []
    for pattern in patterns:
        for m in pattern.finditer(text):
            if any(start <= m.start() < end for start, end in spans):
                continue
            groups = m.groups()
            label, target = (groups[0], groups[1]) if len(groups) > 1 else ("", groups[0])
            target = target.strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            found.append((text[: m.start()].count("\n") + 1, label, target))
    return sorted(found)


def markdown_files(roots: list[Path], excludes: set) -> list[Path]:
    files = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*.md"):
            if excludes & set(path.relative_to(root).parts[:-1]):
                continue
            files.append(path)
    return sorted(set(files))


def probe(url: str, timeout: float) -> tuple[str, str]:
    """Return (status, note). Status is a code, 'ERR', or an exception name."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return str(resp.status), ""
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue  # some hosts reject HEAD, retry as GET
            note = "may be bot filtering, verify in a browser" if exc.code in (401, 403, 429) else ""
            return str(exc.code), note
        except Exception as exc:  # noqa: BLE001 - network errors are all equal here
            if method == "HEAD":
                continue
            return type(exc).__name__, str(exc)[:80]
    return "ERR", "unreachable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="*", default=["."], help="files or directories to scan (default: .)")
    parser.add_argument("--external", action="store_true", help="also probe http(s) URLs")
    parser.add_argument("--timeout", type=float, default=20.0, help="external probe timeout in seconds")
    parser.add_argument("--workers", type=int, default=8, help="parallel external probes")
    parser.add_argument("--exclude", action="append", default=[], help="extra directory name to skip (repeatable)")
    parser.add_argument("--include-images", action="store_true", help="also check image targets")
    parser.add_argument("--quiet", action="store_true", help="print findings only")
    args = parser.parse_args()

    roots = [Path(r).resolve() for r in (args.roots or ["."])]
    for root in roots:
        if not root.exists():
            print(f"error: no such path: {root}", file=sys.stderr)
            return 2

    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    files = markdown_files(roots, excludes)
    base = Path.cwd()

    def show(path: Path) -> str:
        try:
            return str(path.relative_to(base))
        except ValueError:
            return str(path)

    cache: dict = {}
    broken, renderer, external, other = [], [], [], []

    for md in files:
        for line, label, target in links_of(md, args.include_images):
            where = f"{show(md)}:{line}"
            if target.startswith(("http://", "https://")):
                external.append((where, label, target))
                continue
            if target.startswith(("mailto:", "tel:", "#!")):
                continue
            if target.startswith("#"):
                dest, frag = md, unquote(target[1:])
            else:
                parsed = urlparse(target)
                if parsed.scheme:
                    other.append((where, label, target))
                    continue
                frag = unquote(parsed.fragment)
                dest = (md.parent / unquote(parsed.path)).resolve() if parsed.path else md
            if not dest.exists():
                broken.append((where, label, target, "missing file"))
                continue
            if frag and dest.suffix.lower() in (".md", ".markdown"):
                github, gitlab = anchors_of(dest, cache)
                want, want_sq = slug(frag), slug(frag, squeeze=True)
                if want in github or frag.lower() in github:
                    continue
                if want_sq in gitlab or want in gitlab:
                    renderer.append((where, label, target, "anchor resolves on GitLab, not on GitHub"))
                else:
                    broken.append((where, label, target, "missing anchor"))

    if not args.quiet:
        scope = ", ".join(show(r) for r in roots)
        print(f"Scanned {len(files)} Markdown files under {scope}")

    print(f"\nBroken internal links: {len(broken)}")
    for where, label, target, why in broken:
        print(f"  {where}  [{label}]({target})  -> {why}")

    if renderer:
        print(f"\nRenderer-dependent anchors: {len(renderer)}")
        for where, label, target, why in renderer:
            print(f"  {where}  [{label}]({target})  -> {why}")

    failures = []
    if args.external and external:
        urls = sorted({t for _, _, t in external})
        if not args.quiet:
            print(f"\nProbing {len(urls)} unique external URLs...")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = dict(zip(urls, pool.map(lambda u: probe(u, args.timeout), urls)))
        for url in urls:
            status, note = results[url]
            if status.startswith(("2", "3")):
                continue
            for where, label, target in external:
                if target == url:
                    failures.append((where, label, url, status, note))
        print(f"\nExternal URLs not OK: {len(failures)} of {len(urls)} unique")
        for where, label, url, status, note in failures:
            suffix = f"  ({note})" if note else ""
            print(f"  {where}  {status}  {url}{suffix}")
    elif external and not args.quiet:
        print(f"\nExternal URLs: {len({t for _, _, t in external})} unique, not probed (pass --external)")

    if other and not args.quiet:
        print(f"\nSkipped (non-http scheme): {len(other)}")
        for where, label, target in other:
            print(f"  {where}  {target}")

    hard_failures = [f for f in failures if not f[3] in ("401", "403", "429")]
    return 1 if broken or hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())
