import CodeBlock from "../source/CodeBlock";
import styles from "./ProductPreview.module.css";

const SAMPLE_CODE = `def verify_token(token):
    """Return the user id, or None if invalid."""
    try:
        data = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data.get("sub")`;

/** A static illustration of a cited answer, shown beside the sign-in form. */
export default function ProductPreview() {
  return (
    <figure className={styles.preview}>
      <figcaption className={styles.caption}>Example answer</figcaption>
      <p className={styles.question}>How are access tokens verified?</p>
      <p className={styles.answer}>
        The token is decoded with HS256, and any JWT error returns <code>None</code>.{" "}
        <span className={styles.cite}>auth/jwt_utils.py:22-25</span>
      </p>
      <CodeBlock code={SAMPLE_CODE} startLine={19} highlight={{ start: 22, end: 25 }} className={styles.code} />
    </figure>
  );
}
