import { classNames } from "../../lib/format";
import styles from "./Field.module.css";

export default function Select({ label, className, children, ...props }) {
  return (
    <select className={classNames(styles.select, className)} aria-label={label} {...props}>
      {children}
    </select>
  );
}
