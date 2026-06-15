// House rule: a "---" thematic break before every level-3 heading.
// Every level-3 heading ("### Title") must be immediately preceded by a "---" thematic
// break (blank lines in between are fine). Autofix inserts "\n---\n\n" before the heading;
// the leading blank line prevents the inserted "---" from turning the previous line into a
// setext heading. mdformat normalises the surrounding blank lines afterwards.
//
// Uses the markdown-it token stream: tokens[i - 1] is the preceding block-level token, so
// an "hr" there means a thematic break already precedes the heading.

module.exports = {
  names: ["hr-before-h3"],
  description: "Each level-3 (###) heading must be preceded by a '---' thematic break",
  tags: ["custom", "headings"],
  parser: "markdownit",
  function: function hrBeforeH3(params, onError) {
    const tokens = params.parsers.markdownit.tokens;
    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i];
      if (token.type !== "heading_open" || token.tag !== "h3") {
        continue;
      }
      const previous = tokens[i - 1];
      if (previous && previous.type === "hr") {
        continue;
      }
      onError({
        lineNumber: token.map[0] + 1,
        detail: "Insert a '---' line before this level-3 heading",
        fixInfo: { editColumn: 1, deleteCount: 0, insertText: "\n---\n\n" },
      });
    }
  },
};
