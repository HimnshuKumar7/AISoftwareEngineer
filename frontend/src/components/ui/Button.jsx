import { classNames } from "../../lib/format";
import styles from "./Button.module.css";

/**
 * The one button used across the app. Renders a link when `href` is given.
 * variant: "primary" | "secondary" | "ghost" | "danger";  size: "sm" | "md"
 */
export default function Button({
  variant = "secondary",
  size = "md",
  icon: Icon,
  block = false,
  className,
  children,
  href,
  type = "button",
  ...props
}) {
  const classes = classNames(styles.button, styles[variant], styles[size], block && styles.block, className);
  const content = (
    <>
      {Icon && <Icon className={styles.icon} aria-hidden="true" />}
      {children}
    </>
  );
  if (href) {
    return (
      <a className={classes} href={href} {...props}>
        {content}
      </a>
    );
  }
  return (
    <button className={classes} type={type} {...props}>
      {content}
    </button>
  );
}
