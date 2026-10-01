// House rule: a table line is at most 256 characters (option "max"). mdformat pads
// every cell to the widest one in its column, so one long cell stretches the whole
// table and the raw source stops being readable side by side. Shorten the cell, or
// move the detail to a footnote below the table ("**[1]**" in the cell, "[1] ..."
// paragraph after it, see docs/LISTING_FUNC.md). Not auto-fixable: it needs judgement.
//
// Dependency-free on purpose: must load inside the davidanson/markdownlint-cli2 Docker
// image, which does not ship extra npm packages.

module.exports = {
  names: ["table-line-length"],
  description: "Table lines are at most 256 characters (shorten, or use a footnote)",
  tags: ["custom", "table"],
  parser: "none",
  function: function tableLineLength(params, onError) {
    const max = Number((params.config && params.config.max) || 256);
    let inFence = false;
    let fenceChar = "";

    params.lines.forEach((line, index) => {
      const fence = line.match(/^\s*(`{3,}|~{3,})/);
      if (fence) {
        const char = fence[1][0];
        if (!inFence) {
          inFence = true;
          fenceChar = char;
        } else if (char === fenceChar) {
          inFence = false;
          fenceChar = "";
        }
        return;
      }
      if (inFence || !/^\s*\|/.test(line)) {
        return;
      }
      if (line.length > max) {
        onError({
          lineNumber: index + 1,
          detail: `Table line is ${line.length} characters, max ${max}: shorten the cell or move the detail to a footnote`,
          range: [max + 1, line.length - max],
        });
      }
    });
  },
};
