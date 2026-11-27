import { classNames } from "../../lib/format";
import styles from "./Spinner.module.css";

/** `fill` centres the spinner in all the available space. */
export default function Spinner({ fill = false, label = "Loading" }) {
  return (
    <div className={classNames(fill && styles.fill)} role="status">
      <div className={styles.spinner} />
      <span className="sr-only">{label}</span>
    </div>
  );
}
