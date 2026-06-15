// House rule: use a plain hyphen "-" instead of an "en dash" or "em dash".
// Covers U+2010..U+2015 (hyphen, non-breaking hyphen, figure/en/em dash, horizontal bar)
// and U+2212 (minus sign). Line-based so it can pinpoint the exact column for autofix;
// fenced code blocks and inline code spans are skipped to avoid touching code samples.
//
// Dependency-free on purpose: must load inside the davidanson/markdownlint-cli2 Docker
// image, which does not ship extra npm packages.

const SMART_DASH = /[‐-―−]/;

module.exports = {
  names: ["no-smart-dash"],
  description:
    "Use a plain hyphen '-' instead of an en / em (typographic) dash",
  tags: ["custom", "punctuation"],
  parser: "none",
  function: function noSmartDash(params, onError) {
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
      if (inFence) {
        return;
      }

      let inInlineCode = false;
      for (let column = 0; column < line.length; column++) {
        const char = line[column];
        if (char === "`") {
          inInlineCode = !inInlineCode;
          continue;
        }
        if (!inInlineCode && SMART_DASH.test(char)) {
          const code = char
            .codePointAt(0)
            .toString(16)
            .toUpperCase()
            .padStart(4, "0");
          onError({
            lineNumber: index + 1,
            detail: `Replace en / em dash (U+${code}) with a plain hyphen '-'`,
            range: [column + 1, 1],
            fixInfo: {
              editColumn: column + 1,
              deleteCount: 1,
              insertText: "-",
            },
          });
        }
      }
    });
  },
};
