import AuthForm from "../features/auth/AuthForm";
import ProductPreview from "../features/auth/ProductPreview";
import Brand from "../components/ui/Brand";
import styles from "./AuthPage.module.css";

export default function AuthPage({ mode }) {
  return (
    <main className={styles.page}>
      <section className={styles.intro}>
        <Brand />
        <div className={styles.pitch}>
          <h2 className={styles.headline}>Ask your repository. Check every answer against the code.</h2>
          <p className={styles.copy}>
            Questions about any public GitHub repository, answered from its real code with file and line citations.
          </p>
          <ProductPreview />
        </div>
      </section>

      <section className={styles.formSide}>
        <div className={styles.mobileBrand}>
          <Brand />
          <p>Ask questions about any public GitHub repository, grounded in its real code.</p>
        </div>
        <AuthForm key={mode} mode={mode} />
      </section>
    </main>
  );
}
