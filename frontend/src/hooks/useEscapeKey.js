import { useEffect } from "react";

export function useEscapeKey(active, onEscape) {
  useEffect(() => {
    if (!active) return undefined;
    const onKeyDown = (event) => {
      // An open modal dialog handles Escape itself.
      if (event.key === "Escape" && !document.querySelector("dialog[open]")) onEscape();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [active, onEscape]);
}
