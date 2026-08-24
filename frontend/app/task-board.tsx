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
 * BACKEND-CONFIRMED response — no optimistic fake task state.
 * Status can always be changed via an accessible <select>; no
 * drag-and-drop dependency.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth-context";
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
    <section className="card" aria-busy="true" aria-live="polite">
      <h1 id="board-heading">Tasks</h1>
      <p className="subtitle">Loading tasks…</p>
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

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

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

  const emailFor = useCallback(
    (assigneeId: number | null): string | null =>
      assigneeId === null
        ? null
        : users.find((u) => u.id === assigneeId)?.email ?? null,
    [users],
  );

  // ---- form helpers -------------------------------------------------------

  function openCreate() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setFormError(null);
    setShowForm(true);
  }

  function openEdit(task: Task) {
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
    setShowForm(true);
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
    try {
      // Dedicated endpoint for BOTH roles; payload exactly {status}.
      const updated = await updateTaskStatus(task.id, next, opts);
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch {
      setBoardError(GENERIC_ERROR);
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

  // Loading gate: keep the skeleton until the first refetch settles.
  if (loading) {
    return <BoardSkeleton />;
  }

  if (loadError !== null && tasks.length === 0) {
    return (
      <section className="card" aria-labelledby="board-heading">
        <h1 id="board-heading">Tasks</h1>
        <p className="form-error" role="alert">
          Unable to load tasks. Please try again.
        </p>
        <button type="button" className="primary" onClick={() => void refetch()}>
          Retry
        </button>
      </section>
    );
  }

  return (
    <section className="card board-card" aria-labelledby="board-heading">
      <header className="shell-header">
        <div>
          <h1 id="board-heading">Tasks</h1>
          <p className="subtitle">
            Kanban board · {tasks.length} task{tasks.length === 1 ? "" : "s"}
          </p>
        </div>
        {isPm && (
          <button type="button" className="primary" onClick={openCreate}>
            + New Task
          </button>
        )}
      </header>

      {boardError !== null && (
        <p className="form-error" role="alert">
          {boardError}
        </p>
      )}

      {/* Accessible create/edit dialog (native <dialog>-less MVP pattern) */}
      {showForm && (
        <form className="task-form" onSubmit={(e) => void submitForm(e)} noValidate>
          <h2>{editingId === null ? "New Task" : `Edit Task #${editingId}`}</h2>

          <label htmlFor="t-title">Title *</label>
          <input
            id="t-title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
          />

          <label htmlFor="t-desc">Description</label>
          <textarea
            id="t-desc"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={3}
          />

          <label htmlFor="t-assignee">Assignee</label>
          <select
            id="t-assignee"
            value={String(form.assignee_id)}
            onChange={(e) =>
              setForm({
                ...form,
                assignee_id:
                  e.target.value === "" ? "" : Number(e.target.value),
              })
            }
          >
            <option value="">Unassigned</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.email} ({u.role})
              </option>
            ))}
          </select>

          <label htmlFor="t-priority">Priority *</label>
          <select
            id="t-priority"
            value={String(form.priority)}
            onChange={(e) =>
              setForm({
                ...form,
                priority: e.target.value as "" | TaskPriority,
              })
            }
            required
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

          <label htmlFor="t-status">Status *</label>
          <select
            id="t-status"
            value={String(form.status)}
            onChange={(e) => setForm({ ...form, status: e.target.value as TaskStatus })}
            required
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

          <label htmlFor="t-due">Due date</label>
          <input
            id="t-due"
            type="date"
            value={form.due_date}
            onChange={(e) => setForm({ ...form, due_date: e.target.value })}
          />

          {formError !== null && (
            <p className="form-error" role="alert">
              {formError}
            </p>
          )}

          <div className="form-actions">
            <button
              type="button"
              onClick={closeForm}
              disabled={saving}
            >
              Cancel
            </button>
            <button type="submit" className="primary" disabled={saving}>
              {saving ? "Saving…" : editingId === null ? "Create Task" : "Save Changes"}
            </button>
          </div>
        </form>
      )}

      {/* Accessible delete confirmation */}
      {confirmDeleteId !== null && (
        <div className="confirm-box" role="alertdialog" aria-modal="false">
          <p>Delete task?</p>
          <div className="form-actions">
            <button type="button" onClick={() => setConfirmDeleteId(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => void confirmDelete()}
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* Four-column Kanban — ALWAYS renders all four columns, even when
          empty (an optional empty-state hint sits above the grid). */}
      {tasks.length === 0 && (
        <p className="muted" aria-live="polite">
          No tasks yet{isPm ? " — use “+ New Task” to add the first one." : "."}
        </p>
      )}
      <div className="board" role="list" aria-label="Kanban columns">
        {TASK_STATUSES.map((status) => (
          <div
            key={status}
            className="column"
            role="listitem"
            aria-label={`Column ${STATUS_LABELS[status]} (${byStatus.get(status)?.length ?? 0} tasks)`}
          >
            <h2>
              {STATUS_LABELS[status]}{" "}
              <span className="count">{byStatus.get(status)?.length ?? 0}</span>
            </h2>
            {(byStatus.get(status) ?? []).map((task) => {
                const assigneeEmail = emailFor(task.assignee_id);
                const ownTask =
                  role === "developer" &&
                  user !== null &&
                  task.assignee_id === user.user_id;
                return (
                  <article key={task.id} className="task-card">
                    <h3>{task.title}</h3>
                    <p className="task-meta">
                      <span className={`pill pill-${task.priority}`}>
                        Priority: {PRIORITY_LABELS[task.priority]}
                      </span>
                    </p>
                    <p className="task-meta">
                      {assigneeEmail === null ? (
                        <span className="muted">Unassigned</span>
                      ) : (
                        <span>Assignee: {assigneeEmail}</span>
                      )}
                    </p>
                    {task.due_date !== null && (
                      <p className="task-meta">
                        Due: <time dateTime={task.due_date}>{task.due_date}</time>
                      </p>
                    )}
                    <div className="task-actions">
                      {isPm || ownTask ? (
                        <label>
                          <span className="visually-hidden">
                            Status for {task.title}
                          </span>
                          <select
                            aria-label={`Change status of ${task.title}`}
                            value={task.status}
                            onChange={(e) =>
                              void changeStatus(task, e.target.value as TaskStatus)
                            }
                          >
                            {TASK_STATUSES.map((s) => (
                              <option key={s} value={s}>
                                {STATUS_LABELS[s]}
                              </option>
                            ))}
                          </select>
                        </label>
                      ) : (
                        // Unauthorized Developer tasks: status as read-only
                        // text — NO mutation control rendered at all.
                        <p className="task-meta">
                          Status: {STATUS_LABELS[task.status]}
                        </p>
                      )}
                      {isPm && (
                        <>
                          <button
                            type="button"
                            onClick={() => openEdit(task)}
                            aria-label={`Edit ${task.title}`}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteId(task.id)}
                            aria-label={`Delete ${task.title}`}
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
          </div>
        ))}
      </div>
    </section>
  );
}

export { BoardSkeleton };
