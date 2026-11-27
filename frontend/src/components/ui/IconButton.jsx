import { classNames } from "../../lib/format";
import styles from "./IconButton.module.css";

/** Square, icon-only button. `label` is the accessible name and tooltip. */
export default function IconButton({ icon: Icon, label, className, ...props }) {
  return (
    <button type="button" className={classNames(styles.button, className)} aria-label={label} title={label} {...props}>
      <Icon className={styles.icon} aria-hidden="true" />
    </button>
  );
}
