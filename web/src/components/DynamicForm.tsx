import { useState } from "react";
import { createSubmission, RuleSetDetail, Submission } from "../api";

interface Props {
  detail: RuleSetDetail;
  onSubmitted: (submission: Submission) => void;
}

export function DynamicForm({ detail, onSubmitted }: Props) {
  const [files, setFiles] = useState<Record<string, File>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (key: string, file: File | null) => {
    setFiles((prev) => {
      const next = { ...prev };
      if (file) {
        next[key] = file;
      } else {
        delete next[key];
      }
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const entries = Object.entries(files).map(([key, file]) => ({ key, file }));
      const submission = await createSubmission(detail.id, entries);
      onSubmitted(submission);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>{detail.name}</h2>
      {detail.categories.map((category) => (
        <div key={category.name}>
          <h3>{category.name}</h3>
          {category.file_requirements.map((req) => (
            <div className="req" key={req.key}>
              <label htmlFor={`file-${req.key}`}>
                {req.name}
                <span className="badge">{req.kind}</span>
              </label>
              {req.description && (
                <div className="desc">{req.description}</div>
              )}
              <input
                id={`file-${req.key}`}
                type="file"
                accept={req.accept}
                onChange={(e) =>
                  handleChange(req.key, e.target.files?.[0] ?? null)
                }
              />
            </div>
          ))}
        </div>
      ))}
      {error && <div className="error">{error}</div>}
      <button type="submit" disabled={submitting}>
        {submitting ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}
