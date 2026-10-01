// House rule: headings are in sentence case, as in the GitHub, Google and Microsoft
// style guides. Only these keep their capital:
//   - the first word, and the first word after ":" "." "?" "!"
//   - acronyms (API, CA) and words with a capital or digit inside (GitHub, OAuth2, S3)
//   - words with "." "/" "_" "@" in them (file names, paths) and code spans
//   - the names in the "keep" list of the config (proper nouns: Swagger, Keycloak, ...),
//     matched as whole words or phrases, case-sensitive
// Everything else gets its first letter lowercased; the rest of the word is left alone.
// Hyphenated words are handled per part (Short-Term -> Short-term, PostgreSQL-Specific
// -> PostgreSQL-specific).
//
// Applies to the <h1> title, to level-2 and level-3 ATX headings, and to the link texts
// of the table of contents, which mirror the headings: every "#anchor" link above the
// first "##" heading, whatever the list is called (broader than toc-complete.cjs, which
// needs the "Table of contents" marker). Anchors are unaffected: GitHub slugs are
// lowercase anyway.
//
// The <h1> is HTML (the h1-html house rule requires that form), so markdownit never
// reports it as a heading and it is matched on the raw line instead. A link to a document
// carries that document's title, so titles and link texts stay in step. The <h2> HTML
// form is left alone: it only ever holds the "Table of contents" marker, which
// toc-complete.cjs matches.
//
// Autofix replaces only the heading text, not the whole line, so it composes with the
// "---" insert of hr-before-h3 on the same line in one --fix pass (markdownlint skips
// overlapping fixes). Add a name to "keep" when a proper noun gets lowercased.

const SENTENCE_END = /[:.?!]$/;
const LEAD_PUNCT = /^[([{"'*_~]+/;
const TRAIL_PUNCT = /[)\]}"'*_~,;:.?!]+$/;

// Split raw heading text into code spans, link destinations, HTML tags (kept verbatim)
// and text (transformed). Order matters: "](url)" before plain text.
const SEGMENT = /(`+)[\s\S]*?\1|\]\([^)]*\)|<[^>]*>/g;

const isKeptAsIs = (part) =>
  !/[a-z]/.test(part) || // acronym, or no letters at all
  /[A-Z0-9]/.test(part.slice(1)) || // capital or digit inside: GitHub, OAuth2, S3
  /[./_@\\]/.test(part); // file name, path, handle

const lowerFirst = (part) => part.charAt(0).toLowerCase() + part.slice(1);

// Lowercase the first letter of a word, part by part for hyphenated words. At a
// sentence start only the first part keeps its capital (Short-Term -> Short-term).
const lowerWord = (core, keep, sentenceStart) =>
  core
    .split("-")
    .map((part, i) => ((i === 0 && sentenceStart) || keep.has(part) || isKeptAsIs(part) ? part : lowerFirst(part)))
    .join("-");

// Keep phrases: "Technical Working Group" keeps all three words when they occur in
// that order. Single words are phrases of length one.
const parseKeep = (config) => {
  const phrases = (config && Array.isArray(config.keep) ? config.keep : []).map((p) => p.split(/\s+/));
  return { words: new Set(phrases.filter((p) => p.length === 1).map((p) => p[0])), phrases };
};

const core = (token) => token.replace(LEAD_PUNCT, "").replace(TRAIL_PUNCT, "");

// Transform one heading (or TOC link text). Segments other than text pass through but
// count as a word, so "`fullAddress` Field" lowercases "Field".
const sentenceCase = (raw, keep) => {
  const segments = [];
  let last = 0;
  for (const match of raw.matchAll(SEGMENT)) {
    if (match.index > last) segments.push({ text: raw.slice(last, match.index) });
    segments.push({ verbatim: match[0] });
    last = match.index + match[0].length;
  }
  if (last < raw.length) segments.push({ text: raw.slice(last) });

  // Flatten to word tokens (whitespace preserved as separate tokens) for phrase matching.
  const tokens = [];
  for (const segment of segments) {
    if (segment.verbatim !== undefined) {
      tokens.push({ raw: segment.verbatim, verbatim: true });
      continue;
    }
    for (const piece of segment.text.split(/(\s+)/)) {
      if (piece === "") continue;
      tokens.push(/^\s+$/.test(piece) ? { raw: piece, space: true } : { raw: piece, core: core(piece) });
    }
  }
  const words = tokens.filter((t) => !t.space);
  words.forEach((word, index) => {
    if (word.verbatim) return;
    for (const phrase of keep.phrases) {
      if (phrase.length < 2) continue;
      if (phrase.every((p, k) => words[index + k] && words[index + k].core === p)) {
        for (let k = 0; k < phrase.length; k++) words[index + k].keep = true;
      }
    }
  });

  let sentenceStart = true;
  const out = tokens.map((token) => {
    if (token.space) return token.raw;
    if (token.verbatim) {
      sentenceStart = false;
      return token.raw;
    }
    const hasLetters = /[A-Za-z]/.test(token.core);
    let result = token.raw;
    if (hasLetters && !token.keep && !keep.words.has(token.core)) {
      result = token.raw.replace(token.core, lowerWord(token.core, keep.words, sentenceStart));
    }
    // A number is a word too: "Finding: 16 of 43" must not capitalize "of".
    if (/[A-Za-z0-9]/.test(token.core)) sentenceStart = false;
    if (SENTENCE_END.test(token.raw)) sentenceStart = true;
    return result;
  });
  return out.join("");
};

module.exports = {
  names: ["heading-sentence-case"],
  description: "Headings use sentence case: only the first word, acronyms, names and code keep a capital",
  tags: ["custom", "headings"],
  parser: "markdownit",
  function: function headingSentenceCase(params, onError) {
    const keep = parseKeep(params.config);
    const lines = params.lines;
    const tokens = params.parsers.markdownit.tokens;

    // text starts at 0-based column "start" of the line; the fix replaces just that span.
    const report = (lineNumber, text, start, what) => {
      const fixed = sentenceCase(text, keep);
      if (fixed === text) return;
      onError({
        lineNumber,
        detail: `Use sentence case in this ${what}: "${fixed}"`,
        fixInfo: { editColumn: start + 1, deleteCount: text.length, insertText: fixed },
      });
    };

    const headings = tokens.filter((t) => t.type === "heading_open" && (t.tag === "h2" || t.tag === "h3"));
    for (const token of headings) {
      const lineNumber = token.map[0] + 1;
      const match = /^(\s{0,3}#{2,3}\s+)(.*?)(\s+#+\s*)?$/.exec(lines[lineNumber - 1]);
      if (!match) continue; // setext heading: nothing to rewrite in place
      report(lineNumber, match[2], match[1].length, "heading");
    }

    // The <h1> title, on its raw line: markdownit reports it as HTML, not as a heading.
    for (let i = 0; i < lines.length; i++) {
      const match = /^(\s*<h1>)(.*?)(<\/h1>\s*)$/.exec(lines[i]);
      if (match) report(i + 1, match[2], match[1].length, "title");
    }

    // TOC link texts: "#anchor" links above the first "##" heading.
    const tocEnd = headings.length > 0 ? headings[0].map[0] : lines.length;
    for (let i = 0; i < tocEnd; i++) {
      for (const match of lines[i].matchAll(/\[([^\]]+)\]\(#/g)) {
        report(i + 1, match[1], match.index + 1, "TOC entry");
      }
    }
  },
};
