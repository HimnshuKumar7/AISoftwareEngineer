import { useState } from "react";
import { GitBranch, Plus } from "lucide-react";
import { errorMessage } from "../../api/client";
import { reposApi } from "../../api/repos";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import IconButton from "../../components/ui/IconButton";
import TextField from "../../components/ui/TextField";
import styles from "./AddRepoForm.module.css";

export default function AddRepoForm({ onAdded }) {
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [showBranch, setShowBranch] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const repo = await reposApi.add(url.trim(), showBranch ? branch.trim() || undefined : undefined);
      setUrl("");
      setBranch("");
      onAdded(repo);
    } catch (err) {
      setError(errorMessage(err, "Could not add the repository."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <TextField
        label="GitHub repository URL"
        hideLabel
        placeholder="https://github.com/owner/repo"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        spellCheck={false}
        autoComplete="off"
      />
      {showBranch && (
        <TextField
          label="Branch"
          hideLabel
          placeholder="Branch (optional)"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          spellCheck={false}
        />
      )}
      <div className={styles.row}>
        <Button
          type="submit"
          variant="primary"
          icon={Plus}
          className={styles.submit}
          disabled={busy || url.trim().length < 10}
        >
          {busy ? "Adding…" : "Index repo"}
        </Button>
        <IconButton
          icon={GitBranch}
          label={showBranch ? "Use default branch" : "Choose branch"}
          aria-pressed={showBranch}
          className={styles.branchToggle}
          onClick={() => setShowBranch((value) => !value)}
        />
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </form>
  );
}
