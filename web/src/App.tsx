import { useEffect, useState } from "react";
import {
  getRuleSet,
  listRuleSets,
  RuleSet,
  RuleSetDetail,
  Submission,
} from "./api";
import { RuleSetSelector } from "./components/RuleSetSelector";
import { DynamicForm } from "./components/DynamicForm";
import { StatusView } from "./components/StatusView";

export default function App() {
  const [ruleSets, setRuleSets] = useState<RuleSet[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RuleSetDetail | null>(null);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRuleSets()
      .then(setRuleSets)
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (selectedId === null) {
      setDetail(null);
      setSubmission(null);
      return;
    }
    setSubmission(null);
    getRuleSet(selectedId)
      .then(setDetail)
      .catch((err) => setError(err.message));
  }, [selectedId]);

  return (
    <div className="container">
      <h1>Dyano Checker</h1>
      {error && <div className="card error">{error}</div>}
      <RuleSetSelector
        ruleSets={ruleSets}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
      {detail && (
        <DynamicForm detail={detail} onSubmitted={setSubmission} />
      )}
      {submission && <StatusView submission={submission} />}
    </div>
  );
}
