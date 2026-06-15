// House rule: use <h1>...</h1> for level-1 headings instead of "#" (so level 1 is
// not pulled into the TOC). ATX level-1 headings ("# Title") are autofixed
// to "<h1>Title</h1>"; setext level-1 headings (underlined with "===") span two lines
// and are reported for manual conversion rather than risk a multi-line rewrite.
//
// Uses the markdown-it token stream so headings inside fenced code blocks are ignored.

module.exports = {
  names: ["h1-html"],
  description: "Level 1 heading must use <h1>...</h1> HTML, not '#'",
  tags: ["custom", "headings"],
  parser: "markdownit",
  function: function h1Html(params, onError) {
    for (const token of params.parsers.markdownit.tokens) {
      if (token.type !== "heading_open" || token.tag !== "h1") {
        continue;
      }
      const lineIndex = token.map[0];
      const source = params.lines[lineIndex];

      if (token.markup === "#") {
        const title = source.replace(/^\s*#\s+/, "").replace(/\s+#+\s*$/, "").trimEnd();
        onError({
          lineNumber: lineIndex + 1,
          detail: "Convert ATX '# ' level-1 heading to <h1>...</h1>",
          fixInfo: { editColumn: 1, deleteCount: source.length, insertText: `<h1>${title}</h1>` },
        });
      } else {
        onError({
          lineNumber: lineIndex + 1,
          detail: "Convert setext level-1 heading to <h1>...</h1> (manual)",
        });
      }
    }
  },
};
