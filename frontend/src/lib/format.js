export const plural = (count, word, pluralWord = `${word}s`) =>
  `${count.toLocaleString()} ${count === 1 ? word : pluralWord}`;

/** "path:12-20", or "path:12" for a single line. */
export const formatLocation = (path, start, end) => `${path}:${start}${end !== start ? `-${end}` : ""}`;

export function splitPath(path) {
  const cut = path.lastIndexOf("/") + 1;
  return { directory: path.slice(0, cut), file: path.slice(cut) };
}

export const classNames = (...names) => names.filter(Boolean).join(" ");
