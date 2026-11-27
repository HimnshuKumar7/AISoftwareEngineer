import { useId } from "react";
import { classNames } from "../../lib/format";
import styles from "./Field.module.css";

/** Labelled text input with an optional hint and a trailing control (e.g. show/hide password). */
export default function TextField({ label, hideLabel = false, optional = false, hint, trailing, ...inputProps }) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={hideLabel ? "sr-only" : styles.label}>
        {label}
        {optional && <span className={styles.optional}> (optional)</span>}
      </label>
      <div className={classNames(styles.control, trailing && styles.hasTrailing)}>
        <input id={id} className={styles.input} aria-describedby={hint ? hintId : undefined} {...inputProps} />
        {trailing && <div className={styles.trailing}>{trailing}</div>}
      </div>
      {hint && (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      )}
    </div>
  );
}
