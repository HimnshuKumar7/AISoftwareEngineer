import { forwardRef } from "react";
import { ScanSearch, SendHorizontal } from "lucide-react";
import Button from "../../components/ui/Button";
import Select from "../../components/ui/Select";
import { QUESTION_MAX_LENGTH, getMode } from "../../lib/constants";
import ModeSwitcher from "./ModeSwitcher";
import styles from "./Composer.module.css";

const Composer = forwardRef(function Composer(
  {
    repoName,
    ready,
    failed,
    busy,
    canSend,
    value,
    onChange,
    onSend,
    mode,
    onModeChange,
    providers,
    provider,
    onProviderChange,
    scanning,
    onScan,
  },
  ref,
) {
  const notReadyText = failed
    ? "Re-index this repository to ask questions."
    : "Waiting for the repository to finish indexing…";

  function handleSubmit(event) {
    event.preventDefault();
    onSend();
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSend();
    }
  }

  return (
    <div className={styles.dock}>
      <form className={styles.composer} onSubmit={handleSubmit}>
        <textarea
          ref={ref}
          className={styles.input}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          maxLength={QUESTION_MAX_LENGTH}
          placeholder={ready ? `${getMode(mode).hint}: ask about ${repoName}…` : notReadyText}
          disabled={!ready}
          aria-label="Your question"
        />
        <div className={styles.toolbar}>
          <ModeSwitcher value={mode} onChange={onModeChange} />
          <div className={styles.actions}>
            {providers.length > 1 && (
              <Select
                label="LLM provider"
                className={styles.provider}
                value={provider}
                onChange={(e) => onProviderChange(e.target.value)}
              >
                <option value="">Default model</option>
                {providers.map((item) => (
                  <option key={item.provider} value={item.provider}>
                    {item.provider}: {item.default_model}
                  </option>
                ))}
              </Select>
            )}
            {mode === "duplicates" && ready && (
              <Button size="sm" icon={ScanSearch} onClick={onScan} disabled={busy}>
                {scanning ? "Scanning…" : "Scan whole repo"}
              </Button>
            )}
            <Button type="submit" size="sm" variant="primary" icon={SendHorizontal} disabled={!canSend}>
              Send
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
});

export default Composer;
