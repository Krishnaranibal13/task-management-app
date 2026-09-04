"use client";

import type { CSSProperties } from "react";
import {
  type DirectoryUser,
  STATUS_LABELS,
  type Task,
  type TaskStatus,
} from "@/lib/tasks-api";
import TaskCard from "./task-card";

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
  return (
    <div
      className="column"
      role="listitem"
      aria-label={`Column ${STATUS_LABELS[status]} (${tasks.length} tasks)`}
      style={
        {
          "--column-accent": statusDotColor(status),
          "--column-bg": statusBgColor(status),
        } as CSSProperties
      }
    >
      <header className="column-header">
        <span className="column-dot" aria-hidden="true" />
        <span className="column-title">{STATUS_LABELS[status]}</span>
        <span className="count-badge">{tasks.length}</span>
      </header>

      <div className="column-cards" role="list">
        {tasks.length === 0 && (
          <div className="column-empty-hint" aria-live="polite">
            <span>No tasks in this stage</span>
          </div>
        )}

        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            users={users}
            role={role}
            user={user}
            isBusy={statusSavingId === task.id}
            onChangeStatus={onChangeStatus}
            onOpenEdit={onOpenEdit}
            onConfirmDelete={onConfirmDelete}
            onOpenComments={onOpenComments}
          />
        ))}
      </div>
    </div>
  );
}
