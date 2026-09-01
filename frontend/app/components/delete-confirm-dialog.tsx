"use client";

import { useEffect, useRef, useState } from "react";
import { Task } from "@/lib/tasks-api";

interface DeleteConfirmDialogProps {
  task: Task;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}

export default function DeleteConfirmDialog({
  task,
  onConfirm,
  onCancel,
}: DeleteConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);
  const [confirming, setConfirming] = useState(false);

  // Focus management - initial focus on Cancel (safe default)
  useEffect(() => {
    previousActiveElement.current = document.activeElement as HTMLElement;
    setTimeout(() => cancelRef.current?.focus(), 0);
    return () => {
      previousActiveElement.current?.focus();
    };
  }, []);

  // Focus trap
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onCancel();
        return;
      }
      if (e.key !== "Tab") return;

      const panel = document.querySelector('[role="alertdialog"]') as HTMLElement;
      if (!panel) return;

      const focusable = panel.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      const first = focusable[0] as HTMLElement;
      const last = focusable[focusable.length - 1] as HTMLElement;

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  // Scroll lock
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  async function handleConfirm() {
    setConfirming(true);
    try {
      await onConfirm();
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="dialog-overlay">
      <div className="dialog-panel dialog-panel--alert" role="alertdialog" aria-modal="true" aria-labelledby="delete-title">
        <header className="dialog-header">
          <h2 id="delete-title" className="dialog-title">Delete task?</h2>
        </header>
        <div className="dialog-body" style={{ paddingTop: "var(--space-4)" }}>
          <p style={{ marginBottom: "var(--space-4)", fontSize: "14px", color: "var(--text-primary)", lineHeight: 1.5 }}>
            You are deleting &ldquo;{task.title}&rdquo;. This permanently removes the task and its comments.
          </p>
        </div>
        <footer className="dialog-footer">
          <button
            ref={cancelRef}
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={confirming}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={handleConfirm}
            disabled={confirming}
            aria-busy={confirming}
          >
            {confirming ? "Deleting…" : "Delete"}
          </button>
        </footer>
      </div>
    </div>
  );
}