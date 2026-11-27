import { classNames } from "../../lib/format";
import { CircleAlert, Info } from "lucide-react";
import styles from "./Alert.module.css";

/** tone: "error" | "info". `banner` stretches it across the top of the app. */
export default function Alert({ tone = "info", banner = false, className, children }) {
  const Icon = tone === "error" ? CircleAlert : Info;
  return (
    <div
      className={classNames(styles.alert, styles[tone], banner && styles.banner, className)}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon className={styles.icon} aria-hidden="true" />
      <div className={styles.body}>{children}</div>
    </div>
  );
}
