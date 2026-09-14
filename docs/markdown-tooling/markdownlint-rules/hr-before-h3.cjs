// House rule: a "---" thematic break before every level-3 heading, except when the
// heading directly follows a level-2 heading. Right under a "##" the break is redundant
// and is reported and removed instead. Blank lines in between are fine either way.
//
// Autofix inserts "\n---\n\n" before a heading that lacks the break; the leading blank
// line prevents the inserted "---" from turning the previous line into a setext heading.
// mdformat normalises the surrounding blank lines afterwards.
//
// Uses the markdown-it token stream: tokens[i - 1] is the preceding block-level token, so
// an "hr" there means a thematic break already precedes the heading, and a "heading_close"
// with tag "h2" means the heading directly follows a level-2 heading.

const isH2Close = (token) => Boolean(token) && token.type === "heading_close" && token.tag === "h2";

module.exports = {
  names: ["hr-before-h3"],
  description:
    "Each level-3 (###) heading must be preceded by a '---' thematic break, unless it directly follows a level-2 (##) heading",
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
      if (isH2Close(previous)) {
        continue;
      }
      if (previous && previous.type === "hr") {
        if (isH2Close(tokens[i - 2])) {
          onError({
            lineNumber: previous.map[0] + 1,
            detail: "Remove this '---' line: the level-3 heading directly follows a level-2 heading",
            fixInfo: { deleteCount: -1 },
          });
        }
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
