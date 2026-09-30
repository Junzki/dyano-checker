import { RuleSet } from "../api";

interface Props {
  ruleSets: RuleSet[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function RuleSetSelector({ ruleSets, selectedId, onSelect }: Props) {
  return (
    <div className="card">
      <label htmlFor="ruleset">Choose a rule set</label>
      <select
        id="ruleset"
        value={selectedId ?? ""}
        onChange={(e) => onSelect(Number(e.target.value))}
      >
        <option value="" disabled>
          Select a rule set…
        </option>
        {ruleSets.map((rs) => (
          <option key={rs.id} value={rs.id}>
            {rs.name}
          </option>
        ))}
      </select>
    </div>
  );
}
