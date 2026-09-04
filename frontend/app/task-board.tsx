"use client";

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
  status: "" as TaskStatus | "",
  due_date: "",
};

function BoardSkeleton() {
  return (
    <section className="board-skeleton" aria-busy="true" aria-live="polite">
      <div className="skeleton-row skeleton-row--title" />
      <div className="summary-grid">
        {Array.from({ length: 5 }).map((_, index) => (
          <div className="summary-card" key={index}>
            <div className="skeleton-row" />
            <div className="skeleton-row skeleton-row--short" />
          </div>
        ))}
      </div>
      <div className="board">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="column" key={index}>
            <div className="skeleton-row" />
            <div className="skeleton-card" />
            <div className="skeleton-card" />
          </div>
        ))}
      </div>
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
        const current = tasks.find((task) => task.id === editingId);
        if (!current) throw new Error("missing task");

        const patch: Record<string, unknown> = {};
        if (form.title.trim() !== current.title) patch.title = form.title.trim();
        if ((form.description || null) !== current.description) {
          patch.description = form.description === "" ? null : form.description;
        }
        if (assigneeValue !== current.assignee_id) patch.assignee_id = assigneeValue;
        if (form.priority !== current.priority) patch.priority = form.priority as TaskPriority;
        if (form.due_date !== (current.due_date ?? "")) patch.due_date = dueDateValue;

        if (Object.keys(patch).length > 0) {
          const updated = await updateTask(editingId, patch, opts);
          setTasks((prev) =>
            prev.map((task) => (task.id === updated.id ? updated : task)),
          );
        }
      }

      closeForm();
    } catch {
      setFormError(GENERIC_ERROR);
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(task: Task, next: TaskStatus) {
    if (next === task.status) return;
    setBoardError(null);
    setStatusSavingId(task.id);

    try {
      const updated = await updateTaskStatus(task.id, next, opts);
      setTasks((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item)),
      );
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
      setTasks((prev) => prev.filter((task) => task.id !== confirmDeleteId));
    } catch {
      setBoardError(GENERIC_ERROR);
    } finally {
      setConfirmDeleteId(null);
    }
  }

  const byStatus = useMemo(() => {
    const map = new Map<TaskStatus, Task[]>();
    for (const status of TASK_STATUSES) map.set(status, []);
    for (const task of tasks) map.get(task.status)?.push(task);
    return map;
  }, [tasks]);

  const summary = useMemo(
    () => ({
      total: tasks.length,
      toDo: byStatus.get("to_do")?.length ?? 0,
      inProgress: byStatus.get("in_progress")?.length ?? 0,
      review: byStatus.get("review")?.length ?? 0,
      done: byStatus.get("done")?.length ?? 0,
    }),
    [tasks.length, byStatus],
  );

  const isPm = role === "pm";
  const canComment = role === "pm" || role === "developer";

  if (loading) return <BoardSkeleton />;

  if (loadError !== null && tasks.length === 0) {
    return (
      <section className="load-failure" aria-labelledby="board-heading">
        <div className="load-failure-icon" aria-hidden="true">!</div>
        <h2 id="board-heading">Unable to load tasks</h2>
        <p>Please check your connection and try again.</p>
        <button type="button" className="btn btn-primary" onClick={() => void refetch()}>
          Retry
        </button>
      </section>
    );
  }

  const summaryCards = [
    { label: "Total Tasks", value: summary.total, tone: "neutral" },
    { label: "To Do", value: summary.toDo, tone: "todo" },
    { label: "In Progress", value: summary.inProgress, tone: "progress" },
    { label: "Review", value: summary.review, tone: "review" },
    { label: "Done", value: summary.done, tone: "done" },
  ];

  return (
    <section className="board-page" aria-labelledby="board-heading">
      <div className="board-hero">
        <div>
          <p className="section-kicker">Task workspace</p>
          <h2 id="board-heading" className="board-heading">
            Plan, prioritize, and keep work moving.
          </h2>
          <p className="board-subheading">
            Kanban board · {tasks.length} task{tasks.length === 1 ? "" : "s"} across four workflow stages
          </p>
        </div>

        {isPm && (
          <button type="button" className="btn btn-primary new-task-btn" onClick={openCreate}>
            <span aria-hidden="true">＋</span>
            New Task
          </button>
        )}
      </div>

      <div className="summary-grid" aria-label="Task summary">
        {summaryCards.map((card) => (
          <article key={card.label} className={`summary-card summary-card--${card.tone}`}>
            <div className="summary-card-top">
              <span className="summary-label">{card.label}</span>
              <span className="summary-dot" aria-hidden="true" />
            </div>
            <strong className="summary-value">{card.value}</strong>
          </article>
        ))}
      </div>

      {boardError !== null && (
        <div className="error-banner" role="alert">
          <span className="error-banner-message">{boardError}</span>
          <button type="button" className="btn btn-secondary error-banner-retry" onClick={() => void refetch()}>
            Retry
          </button>
        </div>
      )}

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

      {confirmDeleteId !== null && (
        <DeleteConfirmDialog
          task={tasks.find((task) => task.id === confirmDeleteId)!}
          onConfirm={confirmDelete}
          onCancel={() => setConfirmDeleteId(null)}
        />
      )}

      {commentsTask !== null && (
        <CommentsPanel
          task={commentsTask}
          users={users}
          canComment={canComment}
          getCsrfToken={getCsrfToken}
          onClose={() => setCommentsTask(null)}
        />
      )}

      <div className="board-section-header">
        <div>
          <h3>Task board</h3>
          <p>Move work forward using the status control on each task.</p>
        </div>
      </div>

      {tasks.length === 0 && (
        <p className="empty-board" aria-live="polite">
          No tasks yet{isPm ? ' — use "New Task" to add the first one.' : "."}
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
