// Mirrors section 4 of references/swarm-contract.md (`swarm status --json`).

export const STATES = [
  "queued",
  "working",
  "blocked",
  "needs-decision",
  "pr-open",
  "fixing",
  "ready",
  "done",
  "archived",
] as const;

export type State = (typeof STATES)[number];

export interface LogEntry {
  ts: string;
  who: string;
  text: string;
}

export interface Question {
  text: string;
  options: { key: string; text: string }[];
  recommended: string | null;
}

export interface WorkItem {
  id: string;
  title: string;
  state: State | string;
  role: string;
  owner: string;
  repo: string;
  branch: string;
  pr: string;
  pr_url: string;
  head: string;
  verified_main: string;
  ci: "success" | "failure" | "pending" | "none" | string;
  threads_open: number;
  review: "APPROVED" | "CHANGES_REQUESTED" | "REVIEW_REQUIRED" | "none" | string;
  merged: boolean;
  needs: string[];
  created: string;
  updated: string;
  session_running: boolean;
  session_last: string;
  brief: string;
  log: LogEntry[];
  findings: string;
  question: Question | null;
  answer: string | null;
  stuck: boolean;
}

export interface Change {
  id: string;
  kind: string;
  detail: string;
}

export interface Decision {
  id: string;
  ts: string;
  work: string;
  question: string;
  answer: string;
}

export interface Run {
  ts: string;
  summary: string;
}

export interface SwarmState {
  home: string;
  generated: string;
  config: { next_id: number; stuck_hours: number; owners: string[]; repos: string[] };
  work: WorkItem[];
  changes: Change[];
  decisions: Decision[];
  runs: Run[];
}
