import { CodeXml } from "lucide-react";
import styles from "./Brand.module.css";

export default function Brand() {
  return (
    <span className={styles.brand}>
      <span className={styles.mark}>
        <CodeXml className={styles.icon} aria-hidden="true" />
      </span>
      <span className={styles.name}>AI Software Engineer</span>
    </span>
  );
}
