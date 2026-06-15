"""SDEP house-style overrides for mdformat.

mdformat is opinionated and renders thematic breaks as a row of 70 underscores.
The SDEP house rules require a plain "---". This parser-extension plugin
overrides only the thematic-break renderer; everything else is left to mdformat
and mdformat-gfm (tables, etc.).
"""

from __future__ import annotations

from collections.abc import Mapping

from markdown_it import MarkdownIt
from mdformat.renderer import RenderContext, RenderTreeNode
from mdformat.renderer.typing import Render


def update_mdit(mdit: MarkdownIt) -> None:
    """No new syntax is added; this plugin only overrides rendering."""


def _render_hr(node: RenderTreeNode, context: RenderContext) -> str:
    return "---"


RENDERERS: Mapping[str, Render] = {"hr": _render_hr}
