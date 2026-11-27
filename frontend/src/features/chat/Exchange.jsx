import Badge from "../../components/ui/Badge";
import styles from "./Exchange.module.css";

/** One question and its response, as a single card. */
export default function Exchange({ question, mode, footer, children }) {
  return (
    <article className={styles.exchange}>
      <header className={styles.question}>
        <h3>{question}</h3>
        {mode && <Badge>{mode}</Badge>}
      </header>
      <div className={styles.answer}>{children}</div>
      {footer && <footer className={styles.footer}>{footer}</footer>}
    </article>
  );
}
