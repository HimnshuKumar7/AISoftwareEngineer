import { useEffect, useId, useRef } from "react";
import Button from "./Button";
import styles from "./ConfirmDialog.module.css";

/** Modal confirmation built on the native <dialog>, which handles focus trapping and Escape. */
export default function ConfirmDialog({ title, children, confirmLabel, busy = false, onConfirm, onCancel }) {
  const dialog = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const node = dialog.current;
    if (!node.open) node.showModal();
    return () => node.close();
  }, []);

  return (
    <dialog
      ref={dialog}
      className={styles.dialog}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
    >
      <h2 id={titleId} className={styles.title}>
        {title}
      </h2>
      <div className={styles.body}>{children}</div>
      <div className={styles.actions}>
        <Button onClick={onCancel} disabled={busy} autoFocus>
          Cancel
        </Button>
        <Button variant="danger" onClick={onConfirm} disabled={busy}>
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
