import Image from "next/image";
import styles from "./page.module.css";

const STACK = [
  { label: "Frontend", value: "Next.js + TypeScript" },
  { label: "Backend", value: "FastAPI (Python)" },
  { label: "Database", value: "MySQL" },
  { label: "Testing", value: "pytest + Playwright" },
];

export default function Home() {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <h1>Task Management MVP</h1>
        <p className={styles.subtitle}>
          Foundation phase — frontend scaffold only. No application features
          are implemented yet.
        </p>
        <dl className={styles.stack}>
          {STACK.map((item) => (
            <div key={item.label} className={styles.stackRow}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
        <a className={styles.apiLink} href="/api/health">
          Backend health check → /api/health
        </a>
      </main>
      <footer className={styles.footer}>
        <Image
          src="/next.svg"
          alt=""
          width={80}
          height={20}
          priority
        />
        <span>Phase 1 — foundation</span>
      </footer>
    </div>
  );
}
