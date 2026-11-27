import { SquarePen } from "lucide-react";
import Button from "../../components/ui/Button";
import Select from "../../components/ui/Select";
import { plural } from "../../lib/format";
import MainHeader from "../workspace/MainHeader";
import RepoActions from "../repositories/RepoActions";
import RepoStatusBadge from "../repositories/RepoStatusBadge";
import styles from "./ChatHeader.module.css";

export default function ChatHeader({
  repo,
  conversations,
  conversationId,
  onOpenConversation,
  onNewChat,
  canStartNew,
  onOpenMenu,
  onRepoUpdated,
  onRepoDeleted,
  onError,
}) {
  const ready = repo.status === "ready";

  return (
    <MainHeader onOpenMenu={onOpenMenu}>
      <div className={styles.heading}>
        <div className={styles.titleRow}>
          <h1 className={styles.title} title={`${repo.owner}/${repo.name}`}>
            <span className={styles.owner}>{repo.owner}/</span>
            {repo.name}
          </h1>
          <RepoStatusBadge status={repo.status} />
        </div>
        {ready && (
          <ul className={styles.stats}>
            <li>{plural(repo.file_count, "file")}</li>
            <li>{plural(repo.chunk_count, "chunk")}</li>
            <li>{plural(Object.keys(repo.languages).length, "language")}</li>
            {repo.commit_sha && (
              <li title="Indexed commit">
                <code>{repo.commit_sha.slice(0, 7)}</code>
              </li>
            )}
          </ul>
        )}
      </div>

      <div className={styles.tools}>
        {conversations.length > 0 && (
          <Select
            label="Conversation history"
            className={styles.history}
            value={conversationId ?? ""}
            onChange={(e) => void onOpenConversation(e.target.value)}
          >
            <option value="">New conversation</option>
            {conversations.map((conversation) => (
              <option key={conversation.conversation_id} value={conversation.conversation_id}>
                {conversation.title}
              </option>
            ))}
          </Select>
        )}
        <Button size="sm" icon={SquarePen} onClick={onNewChat} disabled={!canStartNew}>
          New chat
        </Button>
        <span className={styles.divider} aria-hidden="true" />
        <RepoActions repo={repo} onUpdated={onRepoUpdated} onDeleted={onRepoDeleted} onError={onError} />
      </div>
    </MainHeader>
  );
}
