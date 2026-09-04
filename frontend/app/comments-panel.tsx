"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createComment,
  listComments,
  type Comment,
  type DirectoryUser,
} from "@/lib/tasks-api";

const GENERIC_ERROR = "Unable to load comments. Please try again.";
const POST_ERROR = "Unable to add comment. Please try again.";

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

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const emailFor = useCallback(
    (userId: number): string | null =>
      users.find((user) => user.id === userId)?.email ?? null,
    [users],
  );

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (posting) return;

    const trimmed = content.trim();
    if (!trimmed) return;

    setPostError(null);
    setPosting(true);
    try {
      const created = await createComment(task.id, { content: trimmed }, opts);
      setComments((prev) => [...prev, created]);
      setContent("");
    } catch {
      setPostError(POST_ERROR);
    } finally {
      setPosting(false);
    }
  }

  return (
    <div
      className="comments-overlay"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
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
          <div>
            <p className="dialog-eyebrow">Task discussion</p>
            <h2 id="comments-title" className="comments-title">{task.title}</h2>
          </div>
          <button type="button" className="comments-close" aria-label="Close comments" onClick={onClose}>
            ✕
          </button>
        </header>

        <div className="comments-body">
          {loading && (
            <p className="comments-loading" aria-live="polite" aria-busy="true">
              Loading comments…
            </p>
          )}

          {!loading && loadError !== null && (
            <div className="comments-state">
              <p className="form-error" role="alert">{loadError}</p>
              <button type="button" className="btn btn-secondary" onClick={() => void refetch()}>
                Retry
              </button>
            </div>
          )}

          {!loading && loadError === null && (
            <>
              {comments.length === 0 ? (
                <p className="comments-empty" aria-live="polite">No comments yet.</p>
              ) : (
                <ul className="comment-list" aria-label="Comments">
                  {comments.map((comment) => {
                    const author = emailFor(comment.user_id);
                    return (
                      <li key={comment.id} className="comment-item">
                        <div className="comment-meta">
                          <span>{author ?? "Unknown user"}</span>
                          <time dateTime={comment.created_at}>
                            {formatCommentDate(comment.created_at)}
                          </time>
                        </div>
                        <p className="comment-content">{comment.content}</p>
                      </li>
                    );
                  })}
                </ul>
              )}

              {canComment ? (
                <form className="comment-form" onSubmit={(event) => void submit(event)} noValidate>
                  <label htmlFor="c-content" className="comment-form-label">Add a comment</label>
                  <textarea
                    id="c-content"
                    className="comment-form-textarea"
                    value={content}
                    onChange={(event) => setContent(event.target.value)}
                    rows={3}
                    placeholder="Write a comment…"
                  />
                  {postError !== null && <p className="comment-form-error" role="alert">{postError}</p>}
                  <div className="comment-form-actions">
                    <button type="submit" className="btn btn-primary" disabled={posting || content.trim() === ""}>
                      {posting ? "Posting…" : "Add Comment"}
                    </button>
                  </div>
                </form>
              ) : (
                <p className="comments-readonly-note">Viewing comments is read-only.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
