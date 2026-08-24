"use client";

/**
 * Accessible comments panel for a single Task (Phase 5C).
 *
 * Contract:
 *  - Exactly the two approved backend endpoints via the centralized
 *    client: GET/POST /api/tasks/{task_id}/comments.
 *  - Author identity resolved through the user directory (GET /api/users)
 *    to a readable email; neutral "Unknown user" fallback — never an
 *    invented identity, never a raw user ID as the primary label.
 *  - POST body is exactly {content}; author/task identity come from the
 *    backend session and route. Empty/whitespace submissions blocked.
 *  - No edit/delete/moderation controls exist anywhere (approved MVP).
 *  - Backend-confirmed state only: the exact returned Comment is appended
 *    after a successful POST; no fake IDs/timestamps/authors.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createComment,
  listComments,
  type Comment,
  type DirectoryUser,
} from "@/lib/tasks-api";

const GENERIC_ERROR = "Unable to load comments. Please try again.";
const POST_ERROR = "Unable to add comment. Please try again.";

/** Deterministic created_at formatting (UTC, ISO-like) for stable tests. */
export function formatCommentDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
    `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`
  );
}

interface CommentsPanelProps {
  task: { id: number; title: string };
  users: DirectoryUser[];
  /** Approved-role gate: pm | developer. Unknown roles view-only. */
  canComment?: boolean;
  getCsrfToken?: () => string | null;
  onClose: () => void;
}

export default function CommentsPanel({
  task,
  users,
  canComment = false,
  getCsrfToken,
  onClose,
}: CommentsPanelProps) {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [content, setContent] = useState("");
  const [postError, setPostError] = useState<string | null>(null);
  const [posting, setPosting] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  const opts = useMemo(() => ({ getCsrfToken }), [getCsrfToken]);

  const refetch = useCallback(async () => {
    setLoadError(null);
    setLoading(true);
    try {
      const list = await listComments(task.id, opts);
      setComments(list);
    } catch {
      setLoadError(GENERIC_ERROR);
    } finally {
      setLoading(false);
    }
  }, [task.id, opts]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  // Escape closes the dialog (keyboard behavior).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const emailFor = useCallback(
    (userId: number): string | null =>
      users.find((u) => u.id === userId)?.email ?? null,
    [users],
  );

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (posting) return;
    const trimmed = content.trim();
    if (!trimmed) return; // no empty / whitespace-only submissions
    setPostError(null);
    setPosting(true);
    try {
      const created = await createComment(task.id, { content: trimmed }, opts);
      // Append the EXACT backend-confirmed comment.
      setComments((prev) => [...prev, created]);
      setContent("");
    } catch {
      setPostError(POST_ERROR); // sanitized; nothing appended on failure
    } finally {
      setPosting(false);
    }
  }

  return (
    <div
      className="comments-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="comments-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="comments-title"
      >
        <header className="comments-header">
          {/* Visible task context/title */}
          <h2 id="comments-title">
            Comments · {task.title}
          </h2>
          <button
            type="button"
            className="comments-close"
            aria-label="Close comments"
            onClick={onClose}
          >
            ✕
          </button>
        </header>

        {loading && (
          <p className="muted" aria-live="polite" aria-busy="true">
            Loading comments…
          </p>
        )}

        {!loading && loadError !== null && (
          <>
            <p className="form-error" role="alert">
              {loadError}
            </p>
            <button type="button" onClick={() => void refetch()}>
              Retry
            </button>
          </>
        )}

        {!loading && loadError === null && (
          <>
            {comments.length === 0 ? (
              <p className="muted" aria-live="polite">
                No comments yet.
              </p>
            ) : (
              <ul className="comment-list" aria-label="Comments">
                {comments.map((c) => {
                  const author = emailFor(c.user_id);
                  return (
                    <li key={c.id} className="comment-item">
                      <p className="comment-meta">
                        <strong>{author ?? "Unknown user"}</strong>{" "}
                        <time dateTime={c.created_at}>
                          {formatCommentDate(c.created_at)}
                        </time>
                      </p>
                      <p className="comment-content">{c.content}</p>
                    </li>
                  );
                })}
              </ul>
            )}

            {canComment ? (
              <form className="comment-form" onSubmit={(e) => void submit(e)} noValidate>
                <label htmlFor="c-content">Add a comment</label>
                <textarea
                  id="c-content"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={3}
                />
                {postError !== null && (
                  <p className="form-error" role="alert">
                    {postError}
                  </p>
                )}
                <div className="form-actions">
                  <button
                    type="submit"
                    className="primary"
                    disabled={posting || content.trim() === ""}
                  >
                    {posting ? "Posting…" : "Add Comment"}
                  </button>
                </div>
              </form>
            ) : (
              // Unknown/unapproved role: view-only — NO mutation control.
              <p className="muted">Viewing comments is read-only.</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
