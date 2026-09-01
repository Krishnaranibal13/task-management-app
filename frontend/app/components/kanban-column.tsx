"use client";

import { Task, TaskStatus, STATUS_LABELS, type DirectoryUser } from "@/lib/tasks-api";

interface KanbanColumnProps {
  status: TaskStatus;
  tasks: Task[];
  users: DirectoryUser[];
  role: string | undefined;
  user: { user_id: number } | null;
  onChangeStatus: (task: Task, next: TaskStatus) => void;
  onOpenEdit: (task: Task) => void;
  onConfirmDelete: (taskId: number) => void;
  onOpenComments: (task: Task) => void;
  statusSavingId: number | null;
}

function emailFor(assigneeId: number | null, users: DirectoryUser[]): string | null {
  return assigneeId === null
    ? null
    : users.find((u) => u.id === assigneeId)?.email ?? null;
}

function priorityPillClass(priority: string): string {
  return `priority-pill priority-pill--${priority}`;
}

function statusDotColor(status: TaskStatus): string {
  const colors: Record<TaskStatus, string> = {
    to_do: "var(--status-todo)",
    in_progress: "var(--status-inprogress)",
    review: "var(--status-review)",
    done: "var(--status-done)",
  };
  return colors[status];
}

function statusBgColor(status: TaskStatus): string {
  const colors: Record<TaskStatus, string> = {
    to_do: "var(--status-todo-bg)",
    in_progress: "var(--status-inprogress-bg)",
    review: "var(--status-review-bg)",
    done: "var(--status-done-bg)",
  };
  return colors[status];
}

export default function KanbanColumn({
  status,
  tasks,
  users,
  role,
  user,
  onChangeStatus,
  onOpenEdit,
  onConfirmDelete,
  onOpenComments,
  statusSavingId,
}: KanbanColumnProps) {
  const isPm = role === "pm";

  return (
    <div
      className="column"
      role="listitem"
      aria-label={`Column ${STATUS_LABELS[status]} (${tasks.length} tasks)`}
      style={{ "--column-accent": statusDotColor(status), "--column-bg": statusBgColor(status) } as React.CSSProperties}
    >
      <header className="column-header">
        <span
          className="column-dot"
          style={{ background: statusDotColor(status) }}
          aria-hidden="true"
        />
        <span className="column-title">{STATUS_LABELS[status]}</span>
        <span className="count-badge">{tasks.length}</span>
      </header>
      <div className="column-cards" role="list">
        {tasks.length === 0 && (
          <div className="column-empty-hint" aria-live="polite">
            No tasks
          </div>
        )}
        {tasks.map((task) => {
          const assigneeEmail = emailFor(task.assignee_id, users);
          const ownTask =
            role === "developer" &&
            user !== null &&
            task.assignee_id === user.user_id;
          const isBusy = statusSavingId === task.id;

          return (
            <article
              key={task.id}
              className="task-card"
              role="listitem"
            >
              <h3 className="task-card-title">{task.title}</h3>
              <p className="task-meta">
                <span className={priorityPillClass(task.priority)}>
                  Priority: {STATUS_LABELS[task.priority as TaskStatus] ?? ""}
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
                <p className="task-meta task-due">
                  Due: <time dateTime={task.due_date}>{task.due_date}</time>
                </p>
              )}
              {task.description && (
                <p className="task-description-preview">
                  {task.description}
                </p>
              )}
              <div className="task-actions">
                {isPm || ownTask ? (
                  <label className="task-status-select">
                    <span className="visually-hidden">
                      Change status of {task.title}
                    </span>
                    <select
                      aria-label={`Change status of ${task.title}`}
                      value={task.status}
                      onChange={(e) =>
                        void onChangeStatus(task, e.target.value as TaskStatus)
                      }
                      disabled={isBusy}
                    >
                      {["to_do", "in_progress", "review", "done"].map((s) => (
                        <option key={s} value={s}>
                          {STATUS_LABELS[s as TaskStatus]}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <p className="task-status-readonly">
                    Status: {STATUS_LABELS[task.status]}
                  </p>
                )}
                {isPm && (
                  <>
                    <button
                      type="button"
                      className="task-btn task-btn-edit"
                      onClick={() => onOpenEdit(task)}
                      aria-label={`Edit ${task.title}`}
                      disabled={isBusy}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="task-btn task-btn-delete"
                      onClick={() => onConfirmDelete(task.id)}
                      aria-label={`Delete ${task.title}`}
                      disabled={isBusy}
                    >
                      Delete
                    </button>
                  </>
                )}
                <button
                  type="button"
                  className="task-btn task-btn-comments"
                  onClick={() => onOpenComments(task)}
                  aria-label={`Comments for ${task.title}`}
                >
                  Comments
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}