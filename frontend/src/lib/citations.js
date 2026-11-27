/**
 * @typedef {{ path: string, start: number, end: number }} CiteRef
 */

const CITATION_PART = /^(\S+?):(\d+)(?:-(\d+))?$/;

/** Turn grounded `[path:start-end]` markers into markdown links with a `cite:` scheme (skipping code). */
export function linkifyCitations(markdown) {
  return markdown
    .split(/(```[\s\S]*?```|`[^`\n]+`)/g)
    .map((segment, index) => {
      if (index % 2 === 1) return segment; // code fence or inline code: leave untouched
      return segment.replace(/\[([^[\]\n]{3,400})\]/g, (whole, inner) => {
        const refs = inner.split(/\s*,\s*/).map((part) => CITATION_PART.exec(part.trim()));
        if (!refs.every(Boolean)) return whole;
        return refs
          .map(([, path, start, end]) => {
            const label = end && end !== start ? `${path}:${start}-${end}` : `${path}:${start}`;
            const href = `cite:${encodeURIComponent(path)}:${start}:${end ?? start}`;
            return `[\`${label}\`](${href})`;
          })
          .join(" ");
      });
    })
    .join("");
}

/** @returns {CiteRef | null} */
export function parseCiteHref(href) {
  if (!href || !href.startsWith("cite:")) return null;
  const [, rawPath, start, end] = href.split(":");
  if (!rawPath || !start || !end) return null;
  return { path: decodeURIComponent(rawPath), start: Number(start), end: Number(end) };
}

/**
 * Find the retrieved source that contains (or best overlaps) a cited range.
 * @param {CiteRef} ref
 * @returns {{ source: object, start: number, end: number } | null}
 */
export function resolveSource(sources, ref) {
  let best = null;
  for (const source of sources) {
    if (source.path !== ref.path) continue;
    const overlap = Math.min(ref.end, source.end_line) - Math.max(ref.start, source.start_line) + 1;
    if (overlap > 0 && (!best || overlap > best.overlap)) best = { source, overlap };
  }
  if (!best) return null;
  return {
    source: best.source,
    start: Math.max(ref.start, best.source.start_line),
    end: Math.min(ref.end, best.source.end_line),
  };
}

export function githubBlobUrl(owner, name, sha, path, start, end) {
  const encodedPath = path.split("/").map(encodeURIComponent).join("/");
  const base = `https://github.com/${owner}/${name}/blob/${sha || "HEAD"}/${encodedPath}`;
  // Notebook line numbers refer to the extracted cell view, not the raw JSON file, so no line anchor for them.
  return path.toLowerCase().endsWith(".ipynb") ? base : `${base}#L${start}${end !== start ? `-L${end}` : ""}`;
}
