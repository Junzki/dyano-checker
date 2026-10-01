export interface RuleSet {
  id: number;
  name: string;
}

export interface FileRequirement {
  key: string;
  name: string;
  description: string;
  kind: string;
  accept: string;
}

export interface Category {
  name: string;
  file_requirements: FileRequirement[];
}

export interface RuleSetDetail {
  id: number;
  name: string;
  categories: Category[];
}

export interface Submission {
  id: number;
  status: string;
}

export interface SubmissionFile {
  key: string;
  name: string;
  original_name: string;
}

export interface SubmissionDetail {
  id: number;
  status: string;
  files: SubmissionFile[];
  output_url?: string | null;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    throw new Error(`${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export function listRuleSets(): Promise<RuleSet[]> {
  return request<RuleSet[]>("/api/rulesets");
}

export function getRuleSet(id: number): Promise<RuleSetDetail> {
  return request<RuleSetDetail>(`/api/rulesets/${id}`);
}

export function createSubmission(
  ruleSetId: number,
  files: { key: string; file: File }[]
): Promise<Submission> {
  const formData = new FormData();
  formData.append("rule_set_id", String(ruleSetId));
  const keys: string[] = [];
  for (const { key, file } of files) {
    formData.append("files", file);
    keys.push(key);
  }
  formData.append("keys_json", JSON.stringify(keys));
  return request<Submission>("/api/submissions", {
    method: "POST",
    body: formData,
  });
}

export function getSubmission(id: number): Promise<SubmissionDetail> {
  return request<SubmissionDetail>(`/api/submissions/${id}`);
}
