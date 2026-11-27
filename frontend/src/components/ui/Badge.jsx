import { classNames } from "../../lib/format";
import styles from "./Badge.module.css";

/** tone: "neutral" | "success" | "warning" | "danger" */
export default function Badge({ tone = "neutral", children }) {
  return <span className={classNames(styles.badge, styles[tone])}>{children}</span>;
}
