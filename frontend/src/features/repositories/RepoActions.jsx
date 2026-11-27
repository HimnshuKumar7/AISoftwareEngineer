import { useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { errorMessage } from "../../api/client";
import { reposApi } from "../../api/repos";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import IconButton from "../../components/ui/IconButton";
import { ACTIVE_STATUSES } from "../../lib/constants";

/** Re-index and delete controls for the open repository. Failures are reported through `onError`. */
export default function RepoActions({ repo, onUpdated, onDeleted, onError }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const indexing = ACTIVE_STATUSES.includes(repo.status);

  async function reindex() {
    onError(null);
    setBusy(true);
    try {
      onUpdated(await reposApi.reindex(repo.id));
    } catch (err) {
      onError(errorMessage(err, "Re-index failed"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    onError(null);
    setBusy(true);
    try {
      await reposApi.remove(repo.id);
      onDeleted(repo.id);
    } catch (err) {
      onError(errorMessage(err, "Delete failed"));
      setConfirming(false);
      setBusy(false);
    }
  }

  return (
    <>
      <IconButton icon={RefreshCw} label="Re-index repository" disabled={indexing || busy} onClick={reindex} />
      <IconButton
        icon={Trash2}
        label="Delete repository"
        disabled={indexing || busy}
        onClick={() => setConfirming(true)}
      />
      {confirming && (
        <ConfirmDialog
          title="Delete repository?"
          confirmLabel={busy ? "Deleting…" : "Delete repository"}
          busy={busy}
          onConfirm={remove}
          onCancel={() => setConfirming(false)}
        >
          This removes {repo.owner}/{repo.name}, its index and its chat history.
        </ConfirmDialog>
      )}
    </>
  );
}
