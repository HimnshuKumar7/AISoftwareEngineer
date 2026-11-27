import Alert from "../../components/ui/Alert";
import { getMode } from "../../lib/constants";
import DuplicatesReport from "../duplicates/DuplicatesReport";
import AnswerMessage from "./AnswerMessage";
import Exchange from "./Exchange";
import styles from "./Thread.module.css";

export default function Thread({ items, onOpenSource }) {
  return items.map((item) => {
    switch (item.kind) {
      case "result":
        return <AnswerMessage key={item.id} result={item.result} onOpenSource={onOpenSource} />;
      case "duplicates":
        return <DuplicatesReport key={item.id} report={item.report} />;
      case "pending":
        return (
          <Exchange key={item.id} question={item.question} mode={getMode(item.mode)?.label}>
            <p className={styles.pending}>
              <span className={styles.dots} aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              Planning, retrieving, answering…
            </p>
          </Exchange>
        );
      default:
        return (
          <Exchange key={item.id} question={item.question}>
            <Alert tone="error">{item.message}</Alert>
          </Exchange>
        );
    }
  });
}
