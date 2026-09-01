"use client";

import { Task, TaskStatus, STATUS_LABELS, PRIORITY_LABELS, type DirectoryUser } from "@/lib/tasks-api";

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
    : users.find((u) => u.id === assigneeId)?.email ?? null;
}

function priorityPillClass(priority: string): string {
  return `priority-pill priority-pill--${priority}`;
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
      <h3 className="task-card-title">{task.title}</h3>
      <p className="task-meta">
        <span className={priorityPillClass(task.priority)}>
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
}