// House rule: keep max heading nesting at level 3 ("###"). Headings of level 4 or deeper
// are reported. This is detect-only: the prescribed fix (turn "#### NOK" into a "---" line
// plus bold text) is a structural rewrite that is not safe to apply automatically, so it is
// left for the author to do by hand.
//
// Uses the markdown-it token stream so "####" inside fenced code blocks is not flagged.

module.exports = {
  names: ["max-heading-depth"],
  description: "Headings must not nest deeper than level 3 (###)",
  tags: ["custom", "headings"],
  parser: "markdownit",
  function: function maxHeadingDepth(params, onError) {
    for (const token of params.parsers.markdownit.tokens) {
      if (token.type !== "heading_open") {
        continue;
      }
      const level = Number(token.tag.slice(1));
      if (level >= 4) {
        onError({
          lineNumber: token.map[0] + 1,
          detail: `Heading level ${level} exceeds maximum 3; replace with a '---' line and bold text`,
        });
      }
    }
  },
};
