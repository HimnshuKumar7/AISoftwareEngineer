import styles from "./EmptyState.module.css";

/** Centred message for empty, loading-pipeline and failure screens. */
export default function EmptyState({ icon: Icon, title, description, children }) {
  return (
    <div className={styles.empty}>
      {Icon && (
        <span className={styles.iconWrap}>
          <Icon className={styles.icon} aria-hidden="true" />
        </span>
      )}
      <h2 className={styles.title}>{title}</h2>
      {description && <p className={styles.description}>{description}</p>}
      {children}
    </div>
  );
}
