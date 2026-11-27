import styles from "./ProgressBar.module.css";

export default function ProgressBar({ value, label }) {
  return (
    <div
      className={styles.track}
      role="progressbar"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {/* Keep a sliver visible at 0% so it reads as "started". */}
      <div className={styles.fill} style={{ width: `${Math.max(4, value)}%` }} />
    </div>
  );
}
