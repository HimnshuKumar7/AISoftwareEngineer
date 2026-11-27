import { getMode } from "../../lib/constants";
import AnswerFooter from "./AnswerFooter";
import Exchange from "./Exchange";
import MarkdownAnswer from "./MarkdownAnswer";

export default function AnswerMessage({ result, onOpenSource }) {
  return (
    <Exchange
      question={result.question}
      mode={getMode(result.mode)?.label ?? result.mode}
      footer={<AnswerFooter result={result} onOpenSource={onOpenSource} />}
    >
      <MarkdownAnswer markdown={result.answer} sources={result.sources} onOpenSource={onOpenSource} />
    </Exchange>
  );
}
