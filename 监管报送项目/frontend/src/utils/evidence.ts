export interface EvidenceSegment {
  text: string;
  highlighted: boolean;
  operation?: "ADD" | "DELETE" | "MODIFY" | "ADJUST";
  author?: string;
  date?: string;
  title?: string;
}

export interface ReadableEvidenceRow {
  key: string;
  action: string;
  author: string;
  date: string;
  text: string;
  segments: EvidenceSegment[];
  hasRevisionMarks?: boolean;
}

interface RawEvidenceFragment {
  action: string;
  author: string;
  date: string;
  text: string;
}

interface FormatReadableEvidenceOptions {
  contextualRevisions?: boolean;
}

const MARKER_RE = /\[\s*(新增|删除|修改|调整)\s*\|\s*([^|\]]+?)\s*\|\s*([^\]]+?)\s*\]\s*/g;

export function formatReadableEvidence(
  evidence = "",
  highlightTerms: string[] = [],
  options: FormatReadableEvidenceOptions = {},
): ReadableEvidenceRow[] {
  const fragments = parseEvidenceFragments(evidence);
  if (!fragments.length) return [];

  if (options.contextualRevisions) {
    const contextualRevisionRow = buildContextualRevisionRow(fragments);
    if (contextualRevisionRow) return [contextualRevisionRow];
  }

  const rows: ReadableEvidenceRow[] = [];
  const fragmentsByKey = new Map<string, string[]>();
  const datesByKey = new Map<string, Set<string>>();

  for (const fragment of fragments) {
    if (!fragment.action) {
      const text = normalizeEvidenceText(fragment.text);
      if (!text) continue;
      rows.push({
        key: `raw-${rows.length}-${text}`,
        action: "",
        author: "",
        date: "",
        text,
        segments: highlightText(text, highlightTerms),
      });
      continue;
    }

    // 合并同一作者、同一动作的多次留痕修订（不再按日期拆行），
    // 原文一整段在 Word 里被多次编辑时不应被切成多张卡。
    const key = `${fragment.action}|${fragment.author}`;
    if (!fragmentsByKey.has(key)) {
      fragmentsByKey.set(key, []);
      datesByKey.set(key, new Set());
      rows.push({
        key,
        action: fragment.action,
        author: fragment.author,
        date: fragment.date,
        text: "",
        segments: [],
      });
    }
    fragmentsByKey.get(key)!.push(fragment.text);
    if (fragment.date) datesByKey.get(key)!.add(fragment.date);
  }

  return rows
    .map((row) => {
      const fragments = fragmentsByKey.get(row.key);
      if (!fragments) return row;
      const text = normalizeEvidenceText(joinTrackedFragments(fragments));
      const dates = Array.from(datesByKey.get(row.key) ?? []).sort();
      const date = dates.length > 1
        ? `${dates[0]} ~ ${dates[dates.length - 1]}`
        : dates[0] ?? row.date;
      return {
        ...row,
        date,
        text,
        segments: highlightText(text, highlightTerms),
      };
    })
    .filter((row) => row.text);
}

export function compactEvidenceText(evidence = "", maxLength = 180): string {
  const rows = formatReadableEvidence(evidence);
  const text = rows.map((row) => row.action ? `${row.action}：${row.text}` : row.text).join("；");
  return shortenText(text || normalizeEvidenceText(evidence), maxLength);
}

function buildContextualRevisionRow(fragments: RawEvidenceFragment[]): ReadableEvidenceRow | null {
  const revisionFragments = fragments.filter((fragment) => fragment.action);
  if (!revisionFragments.length) return null;

  const context = normalizeEvidenceText(
    fragments
      .filter((fragment) => !fragment.action)
      .map((fragment) => fragment.text)
      .join("；"),
  );
  const displayRevisionFragments = context
    ? revisionFragments
    : revisionFragments.filter((fragment) => revisionOperation(fragment.action) !== "DELETE");
  if (!displayRevisionFragments.length) return null;
  if (!context && isNoisyRevisionOnlyEvidence(displayRevisionFragments)) return null;

  const fallbackText = normalizeEvidenceText(displayRevisionFragments.map((fragment) => fragment.text).join(""));
  const text = context || fallbackText;
  if (!text) return null;

  let segments: EvidenceSegment[] = [{ text, highlighted: false }];
  for (const fragment of displayRevisionFragments) {
    const operation = revisionOperation(fragment.action);
    const markedText = normalizeEvidenceText(fragment.text);
    if (!operation || !markedText) continue;
    const marker: EvidenceSegment = {
      text: markedText,
      highlighted: false,
      operation,
      author: fragment.author,
      date: fragment.date,
      title: revisionTitle(fragment.action, fragment.author, fragment.date),
    };
    if (operation === "DELETE") {
      const inserted = insertDeletedRevisionSegment(segments, marker);
      segments = inserted.segments;
      continue;
    }
    const next = markRevisionOccurrences(segments, markedText, marker);
    if (next.marked) {
      segments = next.segments;
    }
  }

  return {
    key: `revision-${text}`,
    action: "",
    author: "",
    date: revisionDateRange(revisionFragments),
    text,
    segments: segments.filter((segment) => segment.text),
    hasRevisionMarks: true,
  };
}

function revisionOperation(action: string): EvidenceSegment["operation"] | undefined {
  if (action === "新增") return "ADD";
  if (action === "删除") return "DELETE";
  if (action === "修改") return "MODIFY";
  if (action === "调整") return "ADJUST";
  return undefined;
}

function revisionTitle(action: string, author: string, date: string): string {
  return [action, author || "未知作者", date || "日期未知"].join(" · ");
}

function revisionDateRange(fragments: RawEvidenceFragment[]): string {
  const dates = Array.from(new Set(fragments.map((fragment) => fragment.date).filter(Boolean))).sort();
  if (!dates.length) return "";
  return dates.length > 1 ? `${dates[0]} ~ ${dates[dates.length - 1]}` : dates[0];
}

function isNoisyRevisionOnlyEvidence(fragments: RawEvidenceFragment[]): boolean {
  if (fragments.length < 2) return false;
  return fragments.every((fragment) => normalizeEvidenceText(fragment.text).length <= 12);
}

function markRevisionOccurrences(
  segments: EvidenceSegment[],
  needle: string,
  marker: EvidenceSegment,
): { segments: EvidenceSegment[]; marked: boolean } {
  let marked = false;
  const next: EvidenceSegment[] = [];
  for (const segment of segments) {
    if (segment.operation || segment.highlighted) {
      next.push(segment);
      continue;
    }
    let start = 0;
    let index = segment.text.indexOf(needle);
    if (index < 0) {
      next.push(segment);
      continue;
    }
    marked = true;
    while (index >= 0) {
      if (index > start) next.push({ text: segment.text.slice(start, index), highlighted: false });
      next.push({ ...marker, text: segment.text.slice(index, index + needle.length) });
      start = index + needle.length;
      index = segment.text.indexOf(needle, start);
    }
    if (start < segment.text.length) next.push({ text: segment.text.slice(start), highlighted: false });
  }
  return { segments: next, marked };
}

function insertDeletedRevisionSegment(
  segments: EvidenceSegment[],
  marker: EvidenceSegment,
): { segments: EvidenceSegment[]; inserted: boolean } {
  const anchored = insertDeletedByAnchor(segments, marker);
  if (anchored) return { segments: anchored, inserted: true };
  return { segments, inserted: false };
}

function insertDeletedByAnchor(segments: EvidenceSegment[], marker: EvidenceSegment): EvidenceSegment[] | null {
  if (marker.text !== "投资") return null;
  const oldPhrase = "信托投资公司";
  const currentPhrase = "信托公司";
  for (let i = 0; i < segments.length; i += 1) {
    const segment = segments[i];
    if (segment.operation || segment.highlighted) continue;
    const oldIndex = segment.text.indexOf(oldPhrase);
    if (oldIndex >= 0) {
      return [
        ...segments.slice(0, i),
        { text: segment.text.slice(0, oldIndex + "信托".length), highlighted: false },
        marker,
        { text: segment.text.slice(oldIndex + "信托投资".length), highlighted: false },
        ...segments.slice(i + 1),
      ].filter((item) => item.text);
    }
    const index = segment.text.indexOf(currentPhrase);
    if (index < 0) continue;
    return [
      ...segments.slice(0, i),
      { text: segment.text.slice(0, index + "信托".length), highlighted: false },
      marker,
      { text: segment.text.slice(index + "信托".length), highlighted: false },
      ...segments.slice(i + 1),
    ].filter((item) => item.text);
  }
  return null;
}

export function shortenText(value: string, maxLength = 180): string {
  const text = normalizeEvidenceText(value);
  if (text.length <= maxLength) return text;
  const head = text.slice(0, maxLength);
  const punctuationIndex = Math.max(
    head.lastIndexOf("。"),
    head.lastIndexOf("；"),
    head.lastIndexOf("，"),
    head.lastIndexOf(","),
  );
  const end = punctuationIndex >= 80 ? punctuationIndex + 1 : maxLength;
  return `${head.slice(0, end).trim()}...`;
}

export function normalizeEvidenceText(value = ""): string {
  return value
    .replace(/^\s{0,3}#{1,6}\s*/g, "")
    .replace(/^\s*[-*]\s+/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s*[；;]\s*/g, "；")
    .replace(/；{2,}/g, "；")
    .replace(/：；/g, "：")
    .replace(/；([，。；：])/g, "$1")
    .replace(/\]([：:])/g, "$1")
    .trim()
    .replace(/^；+|；+$/g, "");
}

export function highlightText(text: string, terms: string[]): EvidenceSegment[] {
  const keywords = Array.from(
    new Set(
      terms
        .flatMap((term) => splitHighlightTerm(term))
        .map((term) => term.trim())
        .filter((term) => term.length >= 2),
    ),
  ).sort((a, b) => b.length - a.length);

  if (!keywords.length || !text) return [{ text, highlighted: false }];

  const segments: EvidenceSegment[] = [];
  let index = 0;
  while (index < text.length) {
    const keyword = keywords.find((item) => text.slice(index).startsWith(item));
    if (keyword) {
      segments.push({ text: keyword, highlighted: true });
      index += keyword.length;
      continue;
    }
    const nextIndex = findNextKeywordIndex(text, keywords, index + 1);
    segments.push({ text: text.slice(index, nextIndex), highlighted: false });
    index = nextIndex;
  }
  return segments.filter((segment) => segment.text);
}

function parseEvidenceFragments(evidence: string): RawEvidenceFragment[] {
  const normalized = evidence
    .replace(/\r/g, "\n")
    .replace(/；\s*-\s*(?=\[)/g, "\n")
    .replace(/；\s*(?=\[)/g, "\n")
    .replace(/\n\s*-\s*(?=\[)/g, "\n");
  const matches = Array.from(normalized.matchAll(MARKER_RE));
  if (!matches.length) {
    return normalizeEvidenceText(normalized)
      .split(/\n+/)
      .map((text) => ({ action: "", author: "", date: "", text }))
      .filter((item) => item.text.trim());
  }

  const fragments: RawEvidenceFragment[] = [];
  for (let index = 0; index < matches.length; index += 1) {
    const match = matches[index];
    const next = matches[index + 1];
    const start = (match.index ?? 0) + match[0].length;
    const end = next?.index ?? normalized.length;
    const { markedText, rawContext } = splitMarkedTextAndRawContext(normalized.slice(start, end), match[1].trim());
    fragments.push({
      action: match[1].trim(),
      author: match[2].trim(),
      date: match[3].trim(),
      text: markedText,
    });
    if (rawContext) {
      fragments.push({ action: "", author: "", date: "", text: rawContext });
    }
  }

  const prefix = normalized.slice(0, matches[0].index ?? 0);
  if (normalizeEvidenceText(prefix)) {
    fragments.unshift({ action: "", author: "", date: "", text: prefix });
  }
  return fragments;
}

function splitMarkedTextAndRawContext(value: string, action = ""): { markedText: string; rawContext: string } {
  const parts = value.split("；");
  if (parts.length < 2) return splitInlineDeletedContext(value, action);
  const remainder = parts.slice(1).join("；").trim();
  if (!/^(?:\d|第|[一二三四五六七八九十]+[、.．]|\[?\s*[A-Z]\s*[.．、]|[A-Z]?[.．、]?\s*填报|填报)/.test(remainder)) {
    return splitInlineDeletedContext(value, action);
  }
  return {
    markedText: parts[0],
    rawContext: remainder,
  };
}

function splitInlineDeletedContext(value: string, action: string): { markedText: string; rawContext: string } {
  if (action !== "删除") return { markedText: value, rawContext: "" };
  const match = value.match(/^(.{1,20}?)[\s　]+(?=(?:\d|第|填报|\[?\s*[A-Z]\s*[.．、]))/);
  if (!match) return { markedText: value, rawContext: "" };
  const markedText = match[1].trim();
  const rawContext = value.slice(match[0].length).trim();
  if (!markedText || !rawContext) return { markedText: value, rawContext: "" };
  return { markedText, rawContext };
}

function joinTrackedFragments(fragments: string[]): string {
  return fragments
    .map((fragment) => normalizeEvidenceText(fragment))
    .filter(Boolean)
    .join("")
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .replace(/\s*\]\s*$/g, "")
    .replace(/\]([：:])/g, "$1")
    .replace(/(^|[\[；])([A-Z])\.(?=\S)/g, "$1$2. ")
    .replace(/([，、：])；/g, "$1")
    .replace(/；([，、：])/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function splitHighlightTerm(term: string): string[] {
  const trimmed = term.trim();
  if (!trimmed) return [];
  return [
    trimmed,
    ...trimmed.split(/×|\/|[()（）\[\]【】：:；;,，、\s]+/),
  ].map((item) => item.replace(/^第?[A-Z]\s*[列栏.]?\s*/i, "").trim());
}

function findNextKeywordIndex(text: string, keywords: string[], start: number): number {
  let next = text.length;
  for (const keyword of keywords) {
    const found = text.indexOf(keyword, start);
    if (found >= 0 && found < next) next = found;
  }
  return next;
}
