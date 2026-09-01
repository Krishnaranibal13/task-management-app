"use client";

/**
 * Task board (Phase 5B): four-column Kanban with approved operations.
 *
 * Role model (backend remains authoritative; UI is a UX hint):
 *  - PM: create (+ New Task), edit (all approved fields), delete
 *    (with accessible confirmation), assign/reassign, status changes.
 *  - Developer: view all tasks + readable assignee emails; status
 *    selector ONLY on tasks assigned to them, using the dedicated
 *    /status endpoint with payload exactly {status}.
 *
 * State rule: after every mutation the board updates from the
 * BACKEND-CONFIRMED response â€” no optimistic fake task state.
 * Status can always be changed via an accessible <select>; no
 * drag-and-drop dependency.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import CommentsPanel from "./comments-panel";
import KanbanColumn from "./components/kanban-column";
import TaskFormDialog from "./components/task-form-dialog";
import DeleteConfirmDialog from "./components/delete-confirm-dialog";
import {
  createTask,
  deleteTask,
  listTasks,
  listUsers,
  PRIORITY_LABELS,
  STATUS_LABELS,
  TASK_PRIORITIES,
  TASK_STATUSES,
  updateTask,
  updateTaskStatus,
  type DirectoryUser,
  type Task,
  type TaskPriority,
  type TaskStatus,
} from "@/lib/tasks-api";

const GENERIC_ERROR = "Something went wrong. Please try again.";

const EMPTY_FORM = {
  title: "",
  description: "",
  assignee_id: "" as "" | number,
  priority: "" as "" | TaskPriority,
  // No invented default: the PM must explicitly choose a status.
  status: "" as TaskStatus | "",
  due_date: "",
};

function BoardSkeleton() {
  return (
    <section className="login-card" aria-busy="true" aria-live="polite" style={{ margin: "auto", marginTop: "calc(50vh - 150px)", textAlign: "center" }}>
      <div className="appbar-logo" style={{ justifyContent: "center", marginBottom: "var(--space-4)" }} aria-hidden="true">
        <div className="appbar-logo-mark">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
        </div>
        <h1 className="login-title">Task Management MVP</h1>
      </div>
      <p className="subtitle">Loading tasksâ€¦</p>
    </section>
  );
}

export default function TaskBoard() {
  const { user, getCsrfToken } = useAuth();
  const role = user?.role;

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<DirectoryUser[]>([]);
  const [boardError, setBoardError] = useState<string | null>(null);

    // Explicit dialog-open state: the create/edit dialog must only render when
    // deliberately opened. Deriving it from form-field emptiness is fragile — a
    // fresh Create form is empty, so the dialog would never open (CHG-002).
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [commentsTask, setCommentsTask] = useState<Task | null>(null);
  const [statusSavingId, setStatusSavingId] = useState<number | null>(null);

  const opts = useMemo(() => ({ getCsrfToken }), [getCsrfToken]);

  const refetch = useCallback(async () => {
    setLoadError(null);
    try {
      const [taskList, directory] = await Promise.all([
        listTasks(opts),
        listUsers(opts),
      ]);
      setTasks(taskList);
      setUsers(directory);
    } catch {
      setLoadError(GENERIC_ERROR);
    } finally {
      setLoading(false);
    }
  }, [opts]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  // ---- form helpers -------------------------------------------------------

  function openCreate() {
      setShowForm(true);
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      setFormError(null);
    }

    function openEdit(task: Task) {
      setShowForm(true);
      setEditingId(task.id);
    setForm({
      title: task.title,
      description: task.description ?? "",
      assignee_id: task.assignee_id ?? "",
      priority: task.priority,
      status: task.status,
      due_date: task.due_date ?? "",
    });
    setFormError(null);
  }

  function closeForm() {
      setShowForm(false);
      setEditingId(null);
      setFormError(null);
      setForm({ ...EMPTY_FORM });
    }

  async function submitForm(event: React.FormEvent) {
    event.preventDefault();
    if (saving) return;
    setFormError(null);

    if (!form.title.trim()) {
      setFormError("Title is required.");
      return;
    }
    if (!form.priority) {
      setFormError("Priority is required.");
      return;
    }

    const assigneeValue =
      form.assignee_id === "" ? null : Number(form.assignee_id);
    const dueDateValue = form.due_date === "" ? null : form.due_date;
    setSaving(true);
    try {
      if (editingId === null) {
        // CREATE: all approved fields; required ones explicitly chosen.
        if (!form.status) {
          setFormError("Status is required.");
          setSaving(false);
          return;
        }
        const created = await createTask(
          {
            title: form.title.trim(),
            description: form.description === "" ? null : form.description,
            assignee_id: assigneeValue,
            priority: form.priority as TaskPriority,
            status: form.status as TaskStatus,
            due_date: dueDateValue,
          },
          opts,
        );
        setTasks((prev) => [...prev, created]);
      } else {
        // EDIT (true partial PATCH): send ONLY changed fields. Nullable
        // fields may be explicitly null; required fields never null.
        const current = tasks.find((t) => t.id === editingId);
        if (!current) throw new Error("missing task");
        const patch: Record<string, unknown> = {};
        if (form.title.trim() !== current.title)
          patch.title = form.title.trim();
        if ((form.description || null) !== current.description)
          patch.description = form.description === "" ? null : form.description;
        if (assigneeValue !== current.assignee_id)
          patch.assignee_id = assigneeValue;
        if (form.priority !== current.priority)
          patch.priority = form.priority as TaskPriority;
        if (form.due_date !== (current.due_date ?? ""))
          patch.due_date = dueDateValue;
        if (Object.keys(patch).length > 0) {
          const updated = await updateTask(editingId, patch, opts);
          setTasks((prev) =>
            prev.map((t) => (t.id === updated.id ? updated : t)),
          );
        }
      }
      closeForm();
    } catch {
      setFormError(GENERIC_ERROR); // sanitized; state unchanged on failure
    } finally {
      setSaving(false);
    }
  }

  // ---- mutations ----------------------------------------------------------

  async function changeStatus(task: Task, next: TaskStatus) {
    if (next === task.status) return;
    setBoardError(null);
    setStatusSavingId(task.id);
    try {
      // Dedicated endpoint for BOTH roles; payload exactly {status}.
      const updated = await updateTaskStatus(task.id, next, opts);
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch {
      setBoardError(GENERIC_ERROR);
    } finally {
      setStatusSavingId(null);
    }
  }

  async function confirmDelete() {
    if (confirmDeleteId === null) return;
    setBoardError(null);
    try {
      await deleteTask(confirmDeleteId, opts);
      setTasks((prev) => prev.filter((t) => t.id !== confirmDeleteId));
    } catch {
      setBoardError(GENERIC_ERROR);
    } finally {
      setConfirmDeleteId(null);
    }
  }

  // ---- derived ------------------------------------------------------------

  const byStatus = useMemo(() => {
    const map = new Map<TaskStatus, Task[]>();
    for (const s of TASK_STATUSES) map.set(s, []);
    for (const t of tasks) map.get(t.status)?.push(t);
    return map;
  }, [tasks]);

  const isPm = role === "pm";
  // Phase 5C: explicit approved-role gate. Unknown/unapproved roles get
  // NO comment mutation control (view-only); backend remains authoritative.
  const canComment = role === "pm" || role === "developer";

  // Loading gate: keep the skeleton until the first refetch settles.
  if (loading) {
    return <BoardSkeleton />;
  }

  if (loadError !== null && tasks.length === 0) {
    return (
      <section className="login-card" aria-labelledby="board-heading" style={{ margin: "auto", marginTop: "calc(50vh - 150px)" }}>
        <h1 id="board-heading" className="login-title">Tasks</h1>
        <p className="form-error" role="alert">
          Unable to load tasks. Please try again.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => void refetch()}>
          Retry
        </button>
      </section>
    );
  }

  return (
    <section aria-labelledby="board-heading">
      <header className="toolbar">
        <div>
          <h1 id="board-heading" className="toolbar-title">Tasks</h1>
          <p className="toolbar-subtitle">
            Kanban board Â· {tasks.length} task{tasks.length === 1 ? "" : "s"}
          </p>
        </div>
        {isPm && (
          <div className="toolbar-actions">
            <button type="button" className="btn btn-primary" onClick={openCreate}>
              + New Task
            </button>
          </div>
        )}
      </header>

      {boardError !== null && (
        <div className="error-banner" role="alert">
          <span className="error-banner-message">{boardError}</span>
          <button type="button" className="btn btn-secondary error-banner-retry" onClick={() => void refetch()}>
            Retry
          </button>
        </div>
      )}

      {/* Task create/edit modal dialog — rendered only when explicitly opened */}
            {showForm && (
              <TaskFormDialog
          editingId={editingId}
          form={form}
          setForm={setForm}
          formError={formError}
          saving={saving}
          users={users}
          onSubmit={submitForm}
          onClose={closeForm}
        />
      )}

      {/* Delete confirmation modal alertdialog */}
      {confirmDeleteId !== null && (
        <DeleteConfirmDialog
          task={tasks.find((t) => t.id === confirmDeleteId)!}
          onConfirm={confirmDelete}
          onCancel={() => setConfirmDeleteId(null)}
        />
      )}

      {/* Comments panel modal dialog */}
      {commentsTask !== null && (
        <CommentsPanel
          task={commentsTask}
          users={users}
          canComment={canComment}
          getCsrfToken={getCsrfToken}
          onClose={() => setCommentsTask(null)}
        />
      )}

      {/* Four-column Kanban â€” ALWAYS renders all four columns, even when
          empty (an optional empty-state hint sits above the grid). */}
      {tasks.length === 0 && (
        <p className="empty-board" aria-live="polite">
          No tasks yet{isPm ? ' â€” use "+ New Task" to add the first one.' : "."}
        </p>
      )}
      <div className="board" role="list" aria-label="Kanban columns">
        {TASK_STATUSES.map((status) => (
          <KanbanColumn
            key={status}
            status={status}
            tasks={byStatus.get(status) ?? []}
            users={users}
            role={role}
            user={user}
            onChangeStatus={changeStatus}
            onOpenEdit={openEdit}
            onConfirmDelete={setConfirmDeleteId}
            onOpenComments={setCommentsTask}
            statusSavingId={statusSavingId}
          />
        ))}
      </div>
    </section>
  );
}

export { BoardSkeleton };
