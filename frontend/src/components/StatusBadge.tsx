import type { Repo } from "../types";

const LABEL: Record<Repo["status"], string> = {
  queued: "Queued", cloning: "Cloning", parsing: "Parsing", embedding: "Embedding", indexing: "Indexing",
  ready: "Ready", failed: "Failed",
};

export default function StatusBadge({ status }: { status: Repo["status"] }) {
  return <span className={`badge badge-${status}`}>{LABEL[status]}</span>;
}
