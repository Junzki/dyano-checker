import { useEffect, useState } from "react";
import { getSubmission, Submission, SubmissionDetail } from "../api";

interface Props {
  submission: Submission;
}

export function StatusView({ submission }: Props) {
  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await getSubmission(submission.id);
        if (cancelled) return;
        setDetail(next);
        if (next.status === "completed" || next.status === "failed") return;
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
        return;
      }
      await new Promise((r) => setTimeout(r, 2000));
      void poll();
    };
    void poll();
    return () => {
      cancelled = true;
    };
  }, [submission.id]);

  return (
    <div className="card">
      <h2>Submission #{submission.id}</h2>
      {error && <div className="error">{error}</div>}
      {detail && (
        <>
          <div>
            Status:{" "}
            <span className={`status ${detail.status}`}>{detail.status}</span>
          </div>
          <ul>
            {detail.files.map((f) => (
              <li key={f.key}>
                {f.name} — {f.original_name}
              </li>
            ))}
          </ul>
        </>
      )}
      {!detail && !error && <div>Waiting for status…</div>}
    </div>
  );
}
