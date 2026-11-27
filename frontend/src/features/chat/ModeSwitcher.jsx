import { MODES } from "../../lib/constants";
import styles from "./ModeSwitcher.module.css";

/** Segmented control for the query mode, built on radio buttons for keyboard support. */
export default function ModeSwitcher({ value, onChange }) {
  return (
    <fieldset className={styles.switcher}>
      <legend className="sr-only">Mode</legend>
      {MODES.map((mode) => (
        <label key={mode.id} className={styles.option} title={mode.hint}>
          <input
            type="radio"
            name="mode"
            className="sr-only"
            value={mode.id}
            checked={value === mode.id}
            onChange={() => onChange(mode.id)}
          />
          <span>{mode.label}</span>
        </label>
      ))}
    </fieldset>
  );
}
