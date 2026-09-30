// House rule: in a document with a "Table of Contents", every level-2 (##) and level-3
// (###) heading below it has a TOC link to its anchor. A heading added without its TOC
// entry is invisible to the reader who navigates by the TOC.
//
// The TOC is the region from the "Table of Contents" heading to the first "##" heading;
// the anchors are the "#..." link targets found there. The marker must BE a heading
// (`<h2>Table of Contents</h2>`, or an ATX `## Table of Contents`), not any line holding
// those words: a document that describes this rule mentions them in its prose, and a
// substring match would take that sentence for the start of a TOC.
//
// Heading slugs follow GitHub's rules, the same as scripts/check_dead_links.py: repeated
// slugs get -1, -2, ... in document order.
// GitLab collapses runs of hyphens ("Intern (= vpn)" is #intern--vpn on GitHub, #intern-vpn
// on GitLab), so a repo hosted there links the collapsed form; both count as the entry.
// No autofix: where the entry belongs in the TOC is the author's call.

// The TOC marker: a heading whose only text is "Table of Contents", in the HTML form the
// h1-html house rule produces or as a plain ATX heading.
const TOC_HEADING = /^\s*(?:<h[1-3]>\s*Table of Contents\s*<\/h[1-3]>|#{1,3}\s+Table of Contents\s*)$/;

const slug = (text) => {
  let s = text.replace(/<[^>]+>/g, "");
  s = s.replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1"); // links keep their text
  s = s.replace(/[`*_~]/g, "");
  s = s.normalize("NFKD").toLowerCase().trim();
  s = s.replace(/[^\w\- ]/g, "").replace(/ /g, "-");
  return s;
};

module.exports = {
  names: ["toc-complete"],
  description:
    "Each level-2 (##) and level-3 (###) heading below a 'Table of Contents' must have a TOC link to its anchor",
  tags: ["custom", "headings"],
  parser: "markdownit",
  function: function tocComplete(params, onError) {
    const lines = params.lines;
    const tocLine = lines.findIndex((line) => TOC_HEADING.test(line));
    if (tocLine === -1) {
      return;
    }
    const tokens = params.parsers.markdownit.tokens;
    const headings = tokens
      .map((token, i) => ({ token, i }))
      .filter(({ token }) => token.type === "heading_open" && (token.tag === "h2" || token.tag === "h3"))
      .filter(({ token }) => token.map[0] > tocLine);
    if (headings.length === 0) {
      return;
    }
    const tocEnd = headings[0].token.map[0];
    const anchors = new Set();
    for (const line of lines.slice(tocLine, tocEnd)) {
      for (const match of line.matchAll(/\]\(#([^)]+)\)/g)) {
        anchors.add(match[1]);
      }
    }
    const seen = new Map();
    for (const { token, i } of headings) {
      const base = slug(tokens[i + 1].content);
      const count = seen.get(base) || 0;
      seen.set(base, count + 1);
      const anchor = count === 0 ? base : `${base}-${count}`;
      if (!anchors.has(anchor) && !anchors.has(anchor.replace(/-{2,}/g, "-"))) {
        onError({
          lineNumber: token.map[0] + 1,
          detail: `Add a TOC entry linking to #${anchor}`,
        });
      }
    }
  },
};
