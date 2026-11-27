export const STATUS_LABELS = {
  queued: "Queued",
  cloning: "Cloning",
  parsing: "Parsing",
  embedding: "Embedding",
  indexing: "Indexing",
  ready: "Ready",
  failed: "Failed",
};

/** Statuses of a repository that is still being indexed, in pipeline order. */
export const ACTIVE_STATUSES = ["queued", "cloning", "parsing", "embedding", "indexing"];

export const MODES = [
  {
    id: "qa",
    label: "Ask",
    hint: "Repository-aware Q&A",
    examples: ["How is authentication implemented?", "Where are database connections created?"],
  },
  {
    id: "explain",
    label: "Explain",
    hint: "Document and explain code",
    examples: ["Explain how request routing works", "Document the main entry point"],
  },
  {
    id: "optimize",
    label: "Optimize",
    hint: "Optimization suggestions",
    examples: ["Find performance problems in the data loading code", "How could the main loop be simplified?"],
  },
  {
    id: "duplicates",
    label: "Duplicates",
    hint: "Duplicate-code analysis",
    examples: ["Is there duplicated validation logic?", "Find copy-pasted helper functions"],
  },
];

export const getMode = (id) => MODES.find((mode) => mode.id === id);

export const QUESTION_MIN_LENGTH = 3;
export const QUESTION_MAX_LENGTH = 2000;
export const REPO_POLL_INTERVAL_MS = 2500;
/** Free-tier hosts sleep when idle; after this delay we explain why a request is slow. */
export const SLOW_REQUEST_NOTICE_MS = 6000;
