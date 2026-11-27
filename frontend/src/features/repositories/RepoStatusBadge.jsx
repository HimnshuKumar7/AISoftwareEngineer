import Badge from "../../components/ui/Badge";
import { STATUS_LABELS } from "../../lib/constants";

const TONES = { ready: "success", failed: "danger" };

export default function RepoStatusBadge({ status }) {
  return <Badge tone={TONES[status] ?? "warning"}>{STATUS_LABELS[status] ?? status}</Badge>;
}
