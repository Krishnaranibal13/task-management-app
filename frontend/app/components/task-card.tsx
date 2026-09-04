"use client";

import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  type DirectoryUser,
  type Task,
  type TaskStatus,
} from "@/lib/tasks-api";

interface TaskCardProps {
  task: Task;
  users: DirectoryUser[];
  role: string | undefined;
  user: { user_id: number } | null;
  isBusy: boolean;
  onChangeStatus: (task: Task, next: TaskStatus) => void;
  onOpenEdit: (task: Task) => void;
  onConfirmDelete: (taskId: number) => void;
  onOpenComments: (task: Task) => void;
}

function emailFor(assigneeId: number | null, users: DirectoryUser[]): string | null {
  return assigneeId === null
    ? null
    : users.find((user) => user.id === assigneeId)?.email ?? null;
}

function priorityPillClass(priority: string): string {
  return `priority-pill priority-pill--${priority}`;
}

function avatarText(email: string | null): string {
  if (!email) return "—";
  return email.slice(0, 2).toUpperCase();
}

export default function TaskCard({
  task,
  users,
  role,
  user,
  isBusy,
  onChangeStatus,
  onOpenEdit,
  onConfirmDelete,
  onOpenComments,
}: TaskCardProps) {
  const isPm = role === "pm";
  const assigneeEmail = emailFor(task.assignee_id, users);
  const ownTask =
    role === "developer" &&
    user !== null &&
    task.assignee_id === user.user_id;

  return (
    <article className="task-card" role="listitem">
      <div className="task-card-head">
        <h4 className="task-card-title">{task.title}</h4>
        <span className={priorityPillClass(task.priority)}>
          {PRIORITY_LABELS[task.priority]}
        </span>
      </div>

      {task.description && <p className="task-description-preview">{task.description}</p>}

      <div className="task-card-details">
        <div className="task-assignee">
          <span className="task-avatar" aria-hidden="true">{avatarText(assigneeEmail)}</span>
          <span className="task-assignee-copy">
            <span className="task-detail-label">Assignee</span>
            <span className={assigneeEmail === null ? "muted" : ""} title={assigneeEmail ?? "Unassigned"}>
              {assigneeEmail ?? "Unassigned"}
            </span>
          </span>
        </div>

        {task.due_date !== null && (
          <div className="task-due">
            <span className="task-detail-label">Due</span>
            <time dateTime={task.due_date}>{task.due_date}</time>
          </div>
        )}
      </div>

      <div className="task-actions">
        {isPm || ownTask ? (
          <label className="task-status-select">
            <span className="visually-hidden">Change status of {task.title}</span>
            <select
              aria-label={`Change status of ${task.title}`}
              value={task.status}
              onChange={(event) => void onChangeStatus(task, event.target.value as TaskStatus)}
              disabled={isBusy}
            >
              {["to_do", "in_progress", "review", "done"].map((status) => (
                <option key={status} value={status}>{STATUS_LABELS[status as TaskStatus]}</option>
              ))}
            </select>
          </label>
        ) : (
          <p className="task-status-readonly">Status: {STATUS_LABELS[task.status]}</p>
        )}

        <div className="task-action-buttons">
          {isPm && (
            <>
              <button type="button" className="task-btn task-btn-edit" onClick={() => onOpenEdit(task)} aria-label={`Edit ${task.title}`} disabled={isBusy}>
                Edit
              </button>
              <button type="button" className="task-btn task-btn-delete" onClick={() => onConfirmDelete(task.id)} aria-label={`Delete ${task.title}`} disabled={isBusy}>
                Delete
              </button>
            </>
          )}
          <button type="button" className="task-btn task-btn-comments" onClick={() => onOpenComments(task)} aria-label={`Comments for ${task.title}`}>
            Comments
          </button>
        </div>
      </div>
    </article>
  );
}
