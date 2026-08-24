/**
 * Typed Task + User-directory API functions (Phase 5B).
 *
 * Extends the centralized client WITHOUT scattering fetch() calls:
 * all Task/User requests flow through apiFetch (credentials: include,
 * in-memory CSRF header on mutations, sanitized errors).
 */

import { apiFetch, type ApiClientOptions } from "./api";

/** Approved product values — authoritative, mirrored from the backend. */
export const TASK_STATUSES = [
  "to_do",
  "in_progress",
  "review",
  "done",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const TASK_PRIORITIES = ["low", "medium", "high"] as const;
export type TaskPriority = (typeof TASK_PRIORITIES)[number];

/** Human-readable labels (never sent to the backend). */
export const STATUS_LABELS: Record<TaskStatus, string> = {
  to_do: "To Do",
  in_progress: "In Progress",
  review: "Review",
  done: "Done",
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export interface Task {
  id: number;
  title: string;
  description: string | null;
  assignee_id: number | null;
  priority: TaskPriority;
  status: TaskStatus;
  due_date: string | null; // ISO date (YYYY-MM-DD)
}

export interface DirectoryUser {
  id: number;
  email: string;
  role: "pm" | "developer";
}

export interface TaskCreateInput {
  title: string;
  description?: string | null;
  assignee_id?: number | null;
  priority: TaskPriority;
  status: TaskStatus;
  due_date?: string | null;
}

export type TaskUpdateInput = Partial<{
  title: string;
  description: string | null;
  assignee_id: number | null;
  priority: TaskPriority;
  status: TaskStatus;
  due_date: string | null;
}>;

/** GET /api/users — directory of assignable/identifiable users. */
export function listUsers(options: ApiClientOptions = {}): Promise<DirectoryUser[]> {
  return apiFetch<DirectoryUser[]>("/api/users", options);
}

/** GET /api/tasks */
export function listTasks(options: ApiClientOptions = {}): Promise<Task[]> {
  return apiFetch<Task[]>("/api/tasks", options);
}

/** POST /api/tasks (PM only) */
export function createTask(
  input: TaskCreateInput,
  options: ApiClientOptions = {},
): Promise<Task> {
  return apiFetch<Task>("/api/tasks", { method: "POST", body: input, ...options });
}

/** PATCH /api/tasks/{task_id} (PM only) */
export function updateTask(
  taskId: number,
  patch: TaskUpdateInput,
  options: ApiClientOptions = {},
): Promise<Task> {
  return apiFetch<Task>(`/api/tasks/${taskId}`, {
    method: "PATCH",
    body: patch,
    ...options,
  });
}

/** PATCH /api/tasks/{task_id}/status — payload EXACTLY {status}. */
export function updateTaskStatus(
  taskId: number,
  status: TaskStatus,
  options: ApiClientOptions = {},
): Promise<Task> {
  return apiFetch<Task>(`/api/tasks/${taskId}/status`, {
    method: "PATCH",
    body: { status },
    ...options,
  });
}

/** DELETE /api/tasks/{task_id} (PM only) */
export function deleteTask(taskId: number, options: ApiClientOptions = {}): Promise<void> {
  return apiFetch<void>(`/api/tasks/${taskId}`, { method: "DELETE", ...options });
}
