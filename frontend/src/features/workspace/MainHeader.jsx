import { Menu } from "lucide-react";
import IconButton from "../../components/ui/IconButton";
import styles from "./MainHeader.module.css";

/** Top bar of the main column. On small screens it also opens the repository menu. */
export default function MainHeader({ onOpenMenu, children }) {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <IconButton icon={Menu} label="Open repositories" className={styles.menu} onClick={onOpenMenu} />
        {children}
      </div>
    </header>
  );
}
