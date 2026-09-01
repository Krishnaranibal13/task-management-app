"use client";

import { useEffect, useRef } from "react";
import {
  TASK_PRIORITIES,
  TASK_STATUSES,
  PRIORITY_LABELS,
  STATUS_LABELS,
  type DirectoryUser,
  type TaskPriority,
  type TaskStatus,
} from "@/lib/tasks-api";

interface TaskFormDialogProps {
  editingId: number | null;
  form: {
    title: string;
    description: string;
    assignee_id: "" | number;
    priority: "" | TaskPriority;
    status: TaskStatus | "";
    due_date: string;
  };
  setForm: React.Dispatch<React.SetStateAction<{
    title: string;
    description: string;
    assignee_id: "" | number;
    priority: "" | TaskPriority;
    status: TaskStatus | "";
    due_date: string;
  }>>;
  formError: string | null;
  saving: boolean;
  users: DirectoryUser[];
  onSubmit: (event: React.FormEvent) => Promise<void>;
  onClose: () => void;
}

export default function TaskFormDialog({
  editingId,
  form,
  setForm,
  formError,
  saving,
  users,
  onSubmit,
  onClose,
}: TaskFormDialogProps) {
  const titleRef = useRef<HTMLInputElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Focus management
  useEffect(() => {
    previousActiveElement.current = document.activeElement as HTMLElement;
    // Focus title input on open
    setTimeout(() => titleRef.current?.focus(), 0);
    return () => {
      // Restore focus on close
      previousActiveElement.current?.focus();
    };
  }, []);

  // Focus trap
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;

      const panel = document.querySelector('[role="dialog"]') as HTMLElement;
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
  }, [onClose]);

  // Scroll lock
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  const assigneeValue = form.assignee_id === "" ? "" : String(form.assignee_id);

  return (
    <div className="dialog-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dialog-panel" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
        <header className="dialog-header">
          <h2 id="dialog-title" className="dialog-title">
            {editingId === null ? "New Task" : `Edit Task #${editingId}`}
          </h2>
          <button
            type="button"
            className="dialog-close"
            aria-label="Close dialog"
            onClick={onClose}
            disabled={saving}
          >
            ✕
          </button>
        </header>
        <form className="dialog-body" onSubmit={onSubmit} noValidate>
          <div className="dialog-field">
            <label htmlFor="t-title" className="dialog-field-label">
              Title <span className="required-mark" aria-hidden="true">*</span>
            </label>
            <input
              id="t-title"
              ref={titleRef}
              className="dialog-field-input"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              required
              aria-invalid={formError === "Title is required."}
              aria-describedby={formError === "Title is required." ? "title-error" : undefined}
              disabled={saving}
            />
            {formError === "Title is required." && (
              <p id="title-error" className="dialog-field-error" role="alert">
                {formError}
              </p>
            )}
          </div>

          <div className="dialog-field">
            <label htmlFor="t-desc" className="dialog-field-label">Description</label>
            <textarea
              id="t-desc"
              className="dialog-field-textarea"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              disabled={saving}
            />
          </div>

          <div className="dialog-field">
            <label htmlFor="t-assignee" className="dialog-field-label">Assignee</label>
            <select
              id="t-assignee"
              className="dialog-field-select"
              value={assigneeValue}
              onChange={(e) =>
                setForm({
                  ...form,
                  assignee_id: e.target.value === "" ? "" : Number(e.target.value),
                })
              }
              disabled={saving}
            >
              <option value="">Unassigned</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email} ({u.role === "pm" ? "Project Manager" : "Developer"})
                </option>
              ))}
            </select>
          </div>

          <div className="dialog-field-row">
            <div className="dialog-field">
              <label htmlFor="t-priority" className="dialog-field-label">
                Priority <span className="required-mark" aria-hidden="true">*</span>
              </label>
              <select
                id="t-priority"
                className="dialog-field-select"
                value={form.priority}
                onChange={(e) =>
                  setForm({
                    ...form,
                    priority: e.target.value as "" | TaskPriority,
                  })
                }
                required
                aria-invalid={formError === "Priority is required."}
                aria-describedby={formError === "Priority is required." ? "priority-error" : undefined}
                disabled={saving}
              >
                <option value="" disabled>
                  Select priority…
                </option>
                {TASK_PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_LABELS[p]}
                  </option>
                ))}
              </select>
              {formError === "Priority is required." && (
                <p id="priority-error" className="dialog-field-error" role="alert">
                  {formError}
                </p>
              )}
            </div>

            <div className="dialog-field">
              <label htmlFor="t-status" className="dialog-field-label">
                {editingId === null
                  ? <>
                      Status <span className="required-mark" aria-hidden="true">*</span>
                    </>
                  : "Status (read-only)"}
              </label>
              {editingId === null ? (
                <select
                  id="t-status"
                  className="dialog-field-select"
                  value={form.status}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      status: e.target.value as TaskStatus,
                    })
                  }
                  required
                  aria-invalid={formError === "Status is required."}
                  aria-describedby={formError === "Status is required." ? "status-error" : undefined}
                  disabled={saving}
                >
                  <option value="" disabled>
                    Select status…
                  </option>
                  {TASK_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
              ) : (
                <select
                  id="t-status"
                  className="dialog-field-select"
                  value={form.status}
                  disabled
                  aria-disabled="true"
                >
                  {form.status && (
                    <option value={form.status}>{STATUS_LABELS[form.status]}</option>
                  )}
                </select>
              )}
              {formError === "Status is required." && (
                <p id="status-error" className="dialog-field-error" role="alert">
                  {formError}
                </p>
              )}
            </div>
          </div>

          <div className="dialog-field">
            <label htmlFor="t-due" className="dialog-field-label">Due date</label>
            <input
              id="t-due"
              type="date"
              className="dialog-field-input"
              value={form.due_date}
              onChange={(e) => setForm({ ...form, due_date: e.target.value })}
              disabled={saving}
            />
          </div>

          {formError && formError !== "Title is required." && formError !== "Priority is required." && formError !== "Status is required." && (
            <p className="dialog-field-error" role="alert">
              {formError}
            </p>
          )}

          <footer className="dialog-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving} aria-busy={saving}>
              {saving
                ? "Saving…"
                : editingId === null
                ? "Create Task"
                : "Save Changes"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}