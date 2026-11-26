import type { Source } from "../types";

export interface CiteRef { path: string; start: number; end: number }

const PART = /^(\S+?):(\d+)(?:-(\d+))?$/;

/** Turn grounded `[path:start-end]` markers into markdown links with a `cite:` scheme (skipping code). */
export function linkifyCitations(md: string): string {
  return md
    .split(/(```[\s\S]*?```|`[^`\n]+`)/g)
    .map((seg, i) => {
      if (i % 2 === 1) return seg; // code fence or inline code: leave untouched
      return seg.replace(/\[([^\[\]\n]{3,400})\]/g, (whole, inner: string) => {
        const parts = inner.split(/\s*,\s*/);
        const refs = parts.map((p) => PART.exec(p.trim()));
        if (!refs.every(Boolean)) return whole;
        return refs
          .map((m) => {
            const [, path, s, e] = m!;
            const label = e && e !== s ? `${path}:${s}-${e}` : `${path}:${s}`;
            const href = `cite:${encodeURIComponent(path)}:${s}:${e ?? s}`;
            return `[\`${label}\`](${href})`;
          })
          .join(" ");
      });
    })
    .join("");
}

export function parseCiteHref(href: string | undefined): CiteRef | null {
  if (!href || !href.startsWith("cite:")) return null;
  const [, rawPath, s, e] = href.split(":");
  if (!rawPath || !s || !e) return null;
  return { path: decodeURIComponent(rawPath), start: Number(s), end: Number(e) };
}

/** Find the retrieved source that contains (or best overlaps) a cited range. */
export function resolveSource(sources: Source[], ref: CiteRef): { source: Source; start: number; end: number } | null {
  let best: { source: Source; overlap: number } | null = null;
  for (const s of sources) {
    if (s.path !== ref.path) continue;
    const overlap = Math.min(ref.end, s.end_line) - Math.max(ref.start, s.start_line) + 1;
    if (overlap > 0 && (!best || overlap > best.overlap)) best = { source: s, overlap };
  }
  if (!best) return null;
  return {
    source: best.source,
    start: Math.max(ref.start, best.source.start_line),
    end: Math.min(ref.end, best.source.end_line),
  };
}

export const githubBlobUrl = (owner: string, name: string, sha: string | null | undefined, path: string, s: number, e: number) => {
  const base = `https://github.com/${owner}/${name}/blob/${sha || "HEAD"}/${path.split("/").map(encodeURIComponent).join("/")}`;
  // Notebook line numbers refer to the extracted cell view, not the raw JSON file, so no line anchor for them.
  return path.toLowerCase().endsWith(".ipynb") ? base : `${base}#L${s}${e !== s ? `-L${e}` : ""}`;
};
