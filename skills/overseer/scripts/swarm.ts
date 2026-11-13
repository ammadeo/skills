#!/usr/bin/env -S deno run -A
/**
 * swarm: the work-item ledger behind the overseer skill.
 *
 * Built against references/swarm-contract.md (layout §1, work file §2,
 * commands §3, `status --json` §4). Run `swarm.ts help` for usage.
 */
import { parseArgs } from "@std/cli/parse-args";
import { basename, dirname, fromFileUrl, join, resolve } from "@std/path";
import { parse as parseYaml, stringify as stringifyYaml } from "@std/yaml";

const SCRIPT = fromFileUrl(import.meta.url);
const SKILL_DIR = dirname(dirname(SCRIPT));
const DEFAULT_HOME = join(Deno.env.get("HOME") ?? ".", "swarm");

const STATES = [
  "queued",
  "working",
  "blocked",
  "needs-decision",
  "pr-open",
  "fixing",
  "ready",
  "done",
  "archived",
];
const ROLES = ["builder", "coordinator"];
const BRIEF_ROLES = ["builder", "coordinator", "reviewer"];
const REPORT_KEYS = [
  "state",
  "owner",
  "role",
  "branch",
  "pr",
  "head",
  "verified_main",
  "needs",
];
const SECTIONS = ["Brief", "Log", "Findings", "Question", "Answer"];
const KEY_ORDER = [
  "id",
  "title",
  "state",
  "role",
  "owner",
  "repo",
  "branch",
  "pr",
  "head",
  "verified_main",
  "ci",
  "threads_open",
  "review",
  "merged",
  "needs",
  "state_before",
  "created",
  "updated",
];
const STRING_KEYS = KEY_ORDER.filter(
  (k) => !["threads_open", "merged", "needs"].includes(k),
).concat("session_last");

const SWARM_YML = `next_id: 1            # next W number
auto_commit: true
stuck_hours: 3        # working/fixing with no report/log for this long -> stuck
owners: []            # GitHub owners passed to pr-status.sh --owner
repos: []             # GitHub repos passed to pr-status.sh --repo
bot_reviewer: ""      # login of a review bot, informational
expected_red: []      # "owner/repo: <regex over check names>" lines treated as expected failures
`;

const USAGE =
  `swarm: work-item ledger for the overseer (see references/swarm-contract.md)

Usage: deno run -A ${SCRIPT} <command> [args] [--home DIR] [--who NAME]

  init
  new "<title>" --repo OWNER/NAME [--role builder|coordinator] [--needs W1,W2] [--brief-file F]
  brief W12 [--role builder|coordinator|reviewer]
  report W12 key=value ...        (state owner role branch pr head verified_main needs)
  log W12 "<text>"
  ask W12 "<question>" --option "A: ..." [--option ...] [--recommend A]
  answer W12 "<text>"
  findings W12 < file
  scan [--sessions FILE] [--pr-status CMD]
  changes [--json] [--since REF] [--fail-on KIND,KIND]
  status [--overseer] [--json]
  ready W12 [--allow-behind N]
  done W12 | archive W12
  run-done "<summary>"
  board

Exit codes: 0 ok, 1 check failed, 2 usage, 3 lock.`;

/** An error that ends the command with an exit code; empty message = silent. */
class Fail extends Error {
  constructor(message: string, public code = 2) {
    super(message);
  }
}

type Fm = Record<string, unknown>;
export interface Work {
  path: string;
  fm: Fm;
  sections: Map<string, string>;
}
interface Config {
  next_id: number;
  auto_commit: boolean;
  stuck_hours: number;
  owners: string[];
  repos: string[];
  bot_reviewer: string;
  expected_red: string[];
}
interface LogEntry {
  ts: string;
  who: string;
  text: string;
}
interface Question {
  text: string;
  options: { key: string; text: string }[];
  recommended: string;
}
interface Change {
  id: string;
  kind: string;
  detail: string;
  pr: string;
}
interface Flags {
  home?: string;
  who?: string;
  role?: string;
  needs?: string;
  repo?: string;
  "brief-file"?: string;
  since?: string;
  sessions?: string;
  "pr-status"?: string;
  recommend?: string;
  "fail-on"?: string;
  "allow-behind"?: string;
  option: string[];
  json: boolean;
  overseer: boolean;
  help: boolean;
}
interface Ctx {
  home: string;
  flags: Flags;
  args: string[];
}

// ---------- small helpers ----------

const pad2 = (n: number) => String(n).padStart(2, "0");
function fmtTs(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${
    pad2(d.getHours())
  }:${pad2(d.getMinutes())}`;
}
/** Local `YYYY-MM-DD HH:MM`; SWARM_NOW pins it (tests). */
function now(): string {
  return Deno.env.get("SWARM_NOW") ?? fmtTs(new Date());
}
function parseTs(ts: string): number {
  const m = ts.match(/^(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d)/);
  return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]).getTime() : NaN;
}
function toTs(v: unknown): string {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "string" && !Number.isNaN(parseTs(v)) && v.length === 16) {
    return v;
  }
  const d = new Date(v as string | number);
  return Number.isNaN(d.getTime()) ? String(v) : fmtTs(d);
}
const str = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const oneLine = (s: string) => s.replace(/\s*\n\s*/g, " ").trim();
const firstLine = (s: string) => s.trim().split("\n")[0] ?? "";
function shellQuote(s: string): string {
  return /^[\w@%+=:,./-]+$/.test(s) ? s : `'${s.replaceAll("'", `'\\''`)}'`;
}
function invocation(home: string): string {
  const base = `deno run -A ${shellQuote(SCRIPT)}`;
  return home === DEFAULT_HOME ? base : `${base} --home ${shellQuote(home)}`;
}
function normId(raw: string | undefined): string {
  const m = (raw ?? "").match(/^[Ww]?(\d+)$/);
  if (!m) throw new Fail(`expected a work id like W12, got "${raw ?? ""}"`);
  return `W${m[1]}`;
}
function parseNeeds(v: string): string[] {
  return v.split(",").map((x) => x.trim()).filter(Boolean).map(normId);
}
/** Accepts owner/repo#n, a PR URL, or #n / n (uses the item's repo). */
function normPr(v: string, repo: string): string {
  if (!v) return "";
  const url = v.match(/github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)/);
  if (url) return `${url[1]}#${url[2]}`;
  if (/^[\w.-]+\/[\w.-]+#\d+$/.test(v)) return v;
  const n = v.match(/^#?(\d+)$/);
  if (n && repo) return `${repo}#${n[1]}`;
  throw new Fail(`pr must look like owner/repo#123, got "${v}"`);
}
function splitPr(pr: string): { repo: string; number: string } {
  const [repo, number] = pr.split("#");
  return { repo, number };
}
const prUrl = (pr: string) => {
  if (!pr) return "";
  const { repo, number } = splitPr(pr);
  return `https://github.com/${repo}/pull/${number}`;
};

async function exists(path: string): Promise<boolean> {
  try {
    await Deno.stat(path);
    return true;
  } catch {
    return false;
  }
}
async function readText(path: string): Promise<string | null> {
  try {
    return await Deno.readTextFile(path);
  } catch (e) {
    if (e instanceof Deno.errors.NotFound) return null;
    throw e;
  }
}
/**
 * Reads piped stdin. An agent's shell often leaves stdin open without writing
 * to it, so when nothing (not even EOF) arrives within STDIN_WAIT_MS, it is
 * treated as empty instead of hanging.
 */
async function readStdin(): Promise<string> {
  if (Deno.stdin.isTerminal()) return "";
  const reader = Deno.stdin.readable.getReader();
  const waitMs = Number(Deno.env.get("SWARM_STDIN_WAIT_MS") ?? 1000);
  const first = await Promise.race([
    reader.read(),
    new Promise<null>((r) => setTimeout(() => r(null), waitMs)),
  ]);
  if (first === null || first.done) return "";
  const chunks: Uint8Array<ArrayBuffer>[] = [first.value];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  return await new Blob(chunks).text();
}

async function run(cmd: string, args: string[], cwd?: string) {
  const out = await new Deno.Command(cmd, {
    args,
    cwd,
    stdin: "null",
    stdout: "piped",
    stderr: "piped",
  }).output();
  const dec = new TextDecoder();
  return {
    code: out.code,
    stdout: dec.decode(out.stdout),
    stderr: dec.decode(out.stderr),
  };
}

/** All gh calls go through here; SWARM_GH_STUB=<script> replaces gh (tests). */
export async function gh(args: string[]) {
  try {
    return await run(Deno.env.get("SWARM_GH_STUB") ?? "gh", args);
  } catch (e) {
    return { code: 127, stdout: "", stderr: `cannot run gh: ${e}` };
  }
}

async function git(home: string, ...args: string[]): Promise<string> {
  const r = await run("git", ["-C", home, ...args]);
  if (r.code !== 0) {
    throw new Fail(`git ${args.join(" ")} failed: ${r.stderr.trim()}`, 1);
  }
  return r.stdout;
}

async function commit(home: string, cfg: Config, message: string) {
  if (!cfg.auto_commit) return;
  if (!(await git(home, "status", "--porcelain")).trim()) return;
  await git(home, "add", "-A");
  await git(home, "commit", "-q", "--no-verify", "-m", message);
}

/** Exclusive lock around read-modify-write-commit; waits up to 10 s, then exit 3. */
async function withLock<T>(home: string, fn: () => Promise<T>): Promise<T> {
  const path = join(home, ".swarm", "lock");
  await Deno.mkdir(dirname(path), { recursive: true });
  const deadline = Date.now() +
    Number(Deno.env.get("SWARM_LOCK_WAIT_MS") ?? 10_000);
  while (true) {
    try {
      await Deno.writeTextFile(path, `${Deno.pid}\n`, { createNew: true });
      break;
    } catch (e) {
      if (!(e instanceof Deno.errors.AlreadyExists)) throw e;
      if (Date.now() >= deadline) {
        throw new Fail(
          `swarm is locked by ${path}; retry, or delete it if no swarm command is running`,
          3,
        );
      }
      await new Promise((r) => setTimeout(r, 100));
    }
  }
  try {
    return await fn();
  } finally {
    await Deno.remove(path).catch(() => {});
  }
}

// ---------- config ----------

async function readConfig(home: string): Promise<Config> {
  const text = await readText(join(home, "swarm.yml"));
  if (text === null) {
    throw new Fail(`no swarm at ${home} (run: swarm init --home ${home})`);
  }
  const raw = (parseYaml(text) ?? {}) as Partial<Config>;
  return {
    next_id: Number(raw.next_id ?? 1),
    auto_commit: raw.auto_commit !== false,
    stuck_hours: Number(raw.stuck_hours ?? 3),
    owners: (raw.owners ?? []).map(String),
    repos: (raw.repos ?? []).map(String),
    bot_reviewer: str(raw.bot_reviewer),
    expected_red: (raw.expected_red ?? []).map(String),
  };
}

/** Rewrites only the next_id line so the comments in swarm.yml survive. */
async function setNextId(home: string, n: number) {
  const path = join(home, "swarm.yml");
  const text = (await readText(path)) ?? "";
  const line = `next_id: ${n}`;
  await Deno.writeTextFile(
    path,
    /^next_id:.*$/m.test(text)
      ? text.replace(/^next_id: *\d*/m, line)
      : `${line}\n${text}`,
  );
}

// ---------- work files ----------

export function parseWork(text: string, path: string): Work {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) throw new Fail(`${path}: no YAML front matter`, 1);
  const fm = (parseYaml(m[1]) ?? {}) as Fm;
  for (const k of STRING_KEYS) if (k in fm) fm[k] = str(fm[k]);
  if ("needs" in fm) {
    fm.needs = Array.isArray(fm.needs)
      ? fm.needs.map(String)
      : parseNeeds(str(fm.needs));
  }
  // Only the five known headings split sections, so a Brief may use its own `## ` headings.
  const sections = new Map<string, string>();
  let current: string | null = null;
  let buf: string[] = [];
  const flush = () => current && sections.set(current, buf.join("\n").trim());
  for (const line of m[2].split(/\r?\n/)) {
    const h = line.match(/^## (\S+)\s*$/);
    if (h && SECTIONS.includes(h[1])) {
      flush();
      current = h[1];
      buf = [];
    } else buf.push(line);
  }
  flush();
  return { path, fm, sections };
}

export function renderWork(w: Work): string {
  const ordered: Fm = {};
  for (const k of KEY_ORDER) if (k in w.fm) ordered[k] = w.fm[k];
  for (const k of Object.keys(w.fm)) if (!(k in ordered)) ordered[k] = w.fm[k];
  const yaml = stringifyYaml(ordered, {
    flowLevel: 1,
    lineWidth: -1,
    quoteStyle: '"',
  });
  let out = `---\n${yaml}---\n`;
  for (const name of SECTIONS) {
    const body = w.sections.get(name);
    if (body === undefined && (name === "Question" || name === "Answer")) {
      continue;
    }
    out += `## ${name}\n${body ? `${body}\n` : ""}\n`;
  }
  return out.trimEnd() + "\n";
}

const workPath = (home: string, id: string) => join(home, "work", `${id}.md`);

export async function readWork(home: string, id: string): Promise<Work> {
  const path = workPath(home, id);
  const text = await readText(path);
  if (text === null) throw new Fail(`no work item ${id} in ${home}`);
  return parseWork(text, path);
}

/** Writes the file; `touch` bumps `updated` (scan does not touch). */
export async function writeWork(w: Work, touch = true) {
  if (touch) w.fm.updated = now();
  await Deno.writeTextFile(w.path, renderWork(w));
}

async function listWork(home: string): Promise<Work[]> {
  const dir = join(home, "work");
  const names: string[] = [];
  for await (const e of Deno.readDir(dir)) {
    if (e.isFile && /^W\d+\.md$/.test(e.name)) names.push(e.name);
  }
  names.sort((a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1)));
  const items: Work[] = [];
  for (const n of names) {
    const path = join(dir, n);
    items.push(parseWork(await Deno.readTextFile(path), path));
  }
  return items;
}

const s = (w: Work, key: string) => str(w.fm[key]);

function addLog(w: Work, who: string, text: string) {
  const line = `- ${now()} ${who}: ${oneLine(text)}`;
  const cur = w.sections.get("Log") ?? "";
  w.sections.set("Log", cur ? `${cur}\n${line}` : line);
}

function parseLog(section: string): LogEntry[] {
  const entries: LogEntry[] = [];
  for (const line of section.split("\n")) {
    const m = line.match(/^- (\d{4}-\d\d-\d\d \d\d:\d\d) (.*?): (.*)$/);
    if (m) entries.push({ ts: m[1], who: m[2], text: m[3] });
  }
  // The contract appends, but tolerate hand-written newest-first logs: oldest first, stable.
  return entries
    .map((e, i) => ({ e, i }))
    .sort((a, b) => a.e.ts.localeCompare(b.e.ts) || a.i - b.i)
    .map(({ e }) => e);
}

function parseQuestion(section: string): Question {
  const text: string[] = [];
  const options: Question["options"] = [];
  let recommended = "";
  for (const line of section.split("\n")) {
    const opt = line.match(/^- ([A-Za-z0-9]+): ?(.*)$/);
    const rec = line.match(/^Recommended: *(\S+)/);
    if (opt) options.push({ key: opt[1], text: opt[2] });
    else if (rec) recommended = rec[1];
    else text.push(line);
  }
  return { text: text.join("\n").trim(), options, recommended };
}

function whoFor(ctx: Ctx, w?: Work, fallback?: string): string {
  return ctx.flags.who || Deno.env.get("SWARM_WHO") || fallback ||
    (w && s(w, "role")) || "unknown";
}

function lastActivity(w: Work): string {
  const last = parseLog(w.sections.get("Log") ?? "").at(-1)?.ts ?? "";
  const updated = s(w, "updated");
  return (parseTs(last) || 0) > (parseTs(updated) || 0) ? last : updated;
}

function isStuck(w: Work, cfg: Config, nowMs: number): boolean {
  if (!["working", "fixing"].includes(s(w, "state"))) return false;
  const t = parseTs(lastActivity(w));
  return !Number.isNaN(t) && nowMs - t > cfg.stuck_hours * 3_600_000;
}

const isUnanswered = (w: Work) =>
  s(w, "state") === "needs-decision" && w.sections.has("Question") &&
  !w.sections.get("Answer");

// ---------- commands ----------

async function cmdInit(ctx: Ctx) {
  const { home } = ctx;
  await Deno.mkdir(join(home, "work"), { recursive: true });
  await Deno.mkdir(join(home, ".swarm"), { recursive: true });
  const files: [string, string][] = [
    ["swarm.yml", SWARM_YML],
    ["decisions.md", "# Decisions\n"],
    ["runs.md", "# Runs\n"],
    [".gitignore", ".swarm/\n"],
    ["work/.gitkeep", ""],
  ];
  for (const [name, content] of files) {
    const path = join(home, name);
    if (!(await exists(path))) await Deno.writeTextFile(path, content);
  }
  if (!(await exists(join(home, ".git")))) {
    await git(home, "init", "-q", "-b", "main");
  }
  await git(home, "config", "user.name", "swarm");
  await git(home, "config", "user.email", "swarm@local");
  await git(home, "config", "commit.gpgsign", "false");
  const hasHead =
    (await run("git", ["-C", home, "rev-parse", "-q", "--verify", "HEAD"]))
      .code === 0;
  // The initial commit is always made: `changes` uses it as the default baseline.
  if (!hasHead || (await git(home, "status", "--porcelain")).trim()) {
    await git(home, "add", "-A");
    await git(home, "commit", "-q", "--no-verify", "-m", "init");
  }
  console.log(`swarm home ready: ${home}`);
  console.log(`alias swarm='${invocation(home).replaceAll("'", `'\\''`)}'`);
}

async function cmdNew(ctx: Ctx) {
  const { home, flags } = ctx;
  const title = ctx.args[0];
  if (!title) throw new Fail(`usage: new "<title>" --repo OWNER/NAME`);
  const repo = flags.repo ?? "";
  if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) {
    throw new Fail("new needs --repo OWNER/NAME");
  }
  const role = flags.role ?? "builder";
  if (!ROLES.includes(role)) throw new Fail(`--role must be one of ${ROLES}`);
  const needs = parseNeeds(flags.needs ?? "");
  const brief = flags["brief-file"]
    ? await Deno.readTextFile(flags["brief-file"])
    : await readStdin();
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const id = `W${cfg.next_id}`;
    const path = workPath(home, id);
    if (await exists(path)) {
      throw new Fail(
        `${path} exists but next_id is ${cfg.next_id}; fix swarm.yml`,
        1,
      );
    }
    const ts = now();
    const w: Work = {
      path,
      fm: {
        id,
        title,
        state: "queued",
        role,
        owner: "",
        repo,
        branch: "",
        pr: "",
        head: "",
        verified_main: "",
        ci: "none",
        threads_open: 0,
        review: "none",
        merged: false,
        needs,
        state_before: "",
        created: ts,
        updated: ts,
      },
      sections: new Map([["Brief", brief.trim()], ["Log", ""], [
        "Findings",
        "",
      ]]),
    };
    await writeWork(w, false);
    await setNextId(home, cfg.next_id + 1);
    await commit(home, cfg, `new ${id}`);
    console.log(id);
  });
}

async function cmdBrief(ctx: Ctx) {
  const { home } = ctx;
  const id = normId(ctx.args[0]);
  const w = await readWork(home, id);
  const role = ctx.flags.role ?? s(w, "role");
  if (!BRIEF_ROLES.includes(role)) {
    throw new Fail(`--role must be one of ${BRIEF_ROLES}`);
  }
  const rolesDir = join(SKILL_DIR, "references", "roles");
  const tplPath = join(rolesDir, `${role}.md`);
  const tpl = await readText(tplPath);
  if (tpl === null) {
    throw new Fail(
      `role template not found: ${tplPath}\nexpected templates: ${
        BRIEF_ROLES.map((r) => join(rolesDir, `${r}.md`)).join(", ")
      }`,
    );
  }
  const vars: Record<string, string> = {
    id,
    title: s(w, "title"),
    repo: s(w, "repo"),
    branch: s(w, "branch"),
    pr: s(w, "pr"),
    home,
    swarm: invocation(home),
  };
  const filled = tpl.replace(
    /\{\{(\w+)\}\}/g,
    (m, k: string) => (k in vars ? vars[k] : m),
  );
  console.log(
    `${filled.trimEnd()}\n\n## Brief\n\n${w.sections.get("Brief") ?? ""}`,
  );
}

async function cmdReport(ctx: Ctx) {
  const { home } = ctx;
  const id = normId(ctx.args[0]);
  const pairs = ctx.args.slice(1).map((p) => {
    const i = p.indexOf("=");
    const key = i > 0 ? p.slice(0, i) : "";
    if (!REPORT_KEYS.includes(key)) {
      throw new Fail(
        `report takes key=value with key in: ${
          REPORT_KEYS.join(", ")
        }; got "${p}"`,
      );
    }
    return [key, p.slice(i + 1)] as const;
  });
  if (!pairs.length) throw new Fail("usage: report W12 key=value ...");
  for (const [k, v] of pairs) {
    if (k === "state" && !STATES.includes(v)) {
      throw new Fail(`unknown state "${v}"; states: ${STATES.join(", ")}`);
    }
    if (k === "state" && ["needs-decision", "ready", "archived"].includes(v)) {
      throw new Fail(
        `report cannot set state=${v}; use swarm ${
          { "needs-decision": "ask", ready: "ready", archived: "archive" }[v]
        }`,
      );
    }
    if (k === "role" && !ROLES.includes(v)) {
      throw new Fail(`role must be one of ${ROLES}`);
    }
  }
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const w = await readWork(home, id);
    const shown: string[] = [];
    for (const [k, v] of pairs) {
      const value = k === "needs"
        ? parseNeeds(v)
        : k === "pr"
        ? normPr(v, s(w, "repo"))
        : v;
      w.fm[k] = value;
      shown.push(`${k}=${Array.isArray(value) ? value.join(",") : value}`);
    }
    addLog(w, whoFor(ctx, w), `report ${shown.join(" ")}`);
    await writeWork(w);
    await commit(home, cfg, `report ${id}`);
  });
}

async function cmdLog(ctx: Ctx) {
  const { home } = ctx;
  const id = normId(ctx.args[0]);
  const text = ctx.args.slice(1).join(" ");
  if (!text.trim()) throw new Fail(`usage: log W12 "<text>"`);
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const w = await readWork(home, id);
    addLog(w, whoFor(ctx, w), text);
    await writeWork(w);
    await commit(home, cfg, `log ${id}`);
  });
}

async function cmdAsk(ctx: Ctx) {
  const { home, flags } = ctx;
  const id = normId(ctx.args[0]);
  const question = ctx.args.slice(1).join(" ").trim();
  if (!question) {
    throw new Fail(
      `usage: ask W12 "<question>" --option "A: ..." [--recommend A]`,
    );
  }
  const options = flags.option.map((o) => {
    const m = o.match(/^([A-Za-z0-9]+):\s*(.+)$/);
    if (!m) throw new Fail(`--option must look like "A: text", got "${o}"`);
    return `- ${m[1]}: ${m[2].trim()}`;
  });
  const keys = flags.option.map((o) => o.split(":")[0]);
  if (flags.recommend && !keys.includes(flags.recommend)) {
    throw new Fail(
      `--recommend ${flags.recommend} is not one of the options ${keys}`,
    );
  }
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const w = await readWork(home, id);
    if (s(w, "state") !== "needs-decision") w.fm.state_before = s(w, "state");
    w.fm.state = "needs-decision";
    const lines = [question, ...options];
    if (flags.recommend) lines.push(`Recommended: ${flags.recommend}`);
    w.sections.set("Question", lines.join("\n"));
    // A new question replaces the previous Q/A pair; the old one lives on in decisions.md.
    w.sections.delete("Answer");
    addLog(w, whoFor(ctx, w), `asked: ${firstLine(question)}`);
    await writeWork(w);
    await commit(home, cfg, `ask ${id}`);
  });
}

async function cmdAnswer(ctx: Ctx) {
  const { home } = ctx;
  const id = normId(ctx.args[0]);
  const text = ctx.args.slice(1).join(" ").trim();
  if (!text) throw new Fail(`usage: answer W12 "<text>"`);
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const w = await readWork(home, id);
    const qText = w.sections.get("Question");
    if (!qText || s(w, "state") !== "needs-decision") {
      throw new Fail(`${id} has no open question (state ${s(w, "state")})`);
    }
    const q = parseQuestion(qText);
    // "A", "a: because ...", "B, but ..." pick an option; anything else is free text.
    let answer = text;
    let decision = text;
    const m = text.match(/^([A-Za-z0-9]+)\b[\s:.,;)\u2014-]*([\s\S]*)$/);
    const opt = m &&
      q.options.find((o) => o.key.toUpperCase() === m[1].toUpperCase());
    if (m && opt) {
      const rest = oneLine(m[2]);
      answer = rest ? `${opt.key} — ${rest}` : opt.key;
      const label = opt.text.replace(/\s*\([^)]*\)\s*$/, "");
      decision = `${opt.key} (${label})${rest ? ` — ${rest}` : ""}`;
    }
    const dPath = join(home, "decisions.md");
    const dText = (await readText(dPath)) ?? "# Decisions\n";
    const n = Math.max(
      0,
      ...[...dText.matchAll(/^## D(\d+)/gm)].map((x) => +x[1]),
    ) + 1;
    const entry = `## D${n} (${now()}) ${id}: ${oneLine(q.text)}\nAnswer: ${
      oneLine(decision)
    }\n`;
    await Deno.writeTextFile(dPath, `${dText.trimEnd()}\n\n${entry}`);
    w.sections.set("Answer", answer);
    w.fm.state = s(w, "state_before") || "working";
    w.fm.state_before = "";
    // The answer comes from the user, not from the item's role.
    addLog(w, whoFor(ctx, w, "user"), `answered D${n}: ${oneLine(answer)}`);
    await writeWork(w);
    await commit(home, cfg, `answer ${id}`);
    console.log(`D${n}`);
  });
}

async function cmdFindings(ctx: Ctx) {
  const { home } = ctx;
  const id = normId(ctx.args[0]);
  const text = (await readStdin()).trim();
  if (!text) {
    throw new Fail("findings reads the findings from stdin and got nothing");
  }
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const w = await readWork(home, id);
    const who = whoFor(ctx, w);
    const block = `### ${now()} ${who}\n${text}`;
    const cur = w.sections.get("Findings") ?? "";
    w.sections.set("Findings", cur ? `${cur}\n\n${block}` : block);
    if (s(w, "state") === "pr-open") w.fm.state = "fixing";
    addLog(w, who, `findings: ${firstLine(text).slice(0, 120)}`);
    await writeWork(w);
    await commit(home, cfg, `findings ${id}`);
  });
}

// deno-lint-ignore no-explicit-any
type PrStatus = Record<string, any>;

async function runPrStatus(cfg: Config, custom?: string): Promise<PrStatus[]> {
  const path = join(SKILL_DIR, "scripts", "pr-status.sh");
  if (!custom && !(await exists(path))) {
    throw new Fail(
      `pr-status.sh not found at ${path} (or pass --pr-status CMD)`,
    );
  }
  const cmd = custom ?? `bash ${shellQuote(path)}`;
  const args = [
    "--json",
    ...cfg.owners.flatMap((o) => ["--owner", o]),
    ...cfg.repos.flatMap((r) => ["--repo", r]),
  ];
  const r = await run("sh", ["-c", `${cmd} "$@"`, "sh", ...args]);
  if (r.code !== 0) {
    throw new Fail(`pr-status failed (exit ${r.code}): ${r.stderr.trim()}`, 1);
  }
  try {
    const data = JSON.parse(r.stdout);
    if (!Array.isArray(data)) throw new Error("not an array");
    return data;
  } catch (e) {
    throw new Fail(`pr-status did not print a JSON array: ${e}`, 1);
  }
}

function mapCi(p: PrStatus, cfg: Config): string {
  const state = str(p.ci).toUpperCase();
  if (state === "SUCCESS") return "success";
  if (state === "PENDING" || state === "EXPECTED") return "pending";
  if (state !== "FAILURE" && state !== "ERROR") return "none";
  // A failure counts as green when every failing check matches an expected_red pattern for the repo.
  const patterns = cfg.expected_red.flatMap((line) => {
    const i = line.indexOf(":");
    return i > 0 && line.slice(0, i).trim() === p.repo
      ? [new RegExp(line.slice(i + 1).trim())]
      : [];
  });
  const failing: string[] = p.failingChecks ?? [];
  const expected = patterns.length > 0 && failing.length > 0 &&
    failing.every((name) => patterns.some((re) => re.test(name)));
  return expected ? "success" : "failure";
}

function mapReview(v: unknown): string {
  const r = str(v).toUpperCase();
  return ["APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED"].includes(r)
    ? r
    : "none";
}

async function cmdScan(ctx: Ctx) {
  const { home, flags } = ctx;
  const cfg = await readConfig(home);
  const prs = await runPrStatus(cfg, flags["pr-status"]);
  const byPr = new Map(prs.map((p) => [`${p.repo}#${p.number}`, p]));
  const sessions: PrStatus[] | null = flags.sessions
    ? JSON.parse(await Deno.readTextFile(flags.sessions))
    : null;
  // pr-status.sh lists open PRs only, so a tracked PR missing from it is asked
  // about directly (gh pr view) to learn whether it merged. Done before locking.
  const merged = new Set<string>();
  for (const w of await listWork(home)) {
    const pr = s(w, "pr");
    if (!pr || byPr.has(pr) || ["done", "archived"].includes(s(w, "state"))) {
      continue;
    }
    const { repo, number } = splitPr(pr);
    const r = await gh([
      "pr",
      "view",
      number,
      "-R",
      repo,
      "--json",
      "state",
      "--jq",
      ".state",
    ]);
    if (r.code === 0 && r.stdout.trim() === "MERGED") merged.add(pr);
    else if (r.code !== 0) {
      console.error(`swarm: cannot check ${pr}: ${r.stderr.trim()}`);
    }
  }
  let changed = 0;
  await withLock(home, async () => {
    for (const w of await listWork(home)) {
      const state = s(w, "state");
      if (state === "archived") continue;
      const before = JSON.stringify(w.fm);
      if (state !== "done") {
        const pr = s(w, "pr");
        const p = pr
          ? byPr.get(pr)
          : prs.find((p) =>
            p.repo === s(w, "repo") && s(w, "branch") &&
            p.head === s(w, "branch")
          );
        if (p) {
          if (!pr) w.fm.pr = `${p.repo}#${p.number}`;
          w.fm.ci = mapCi(p, cfg);
          w.fm.threads_open = Number(p.threadsUnresolved ?? 0);
          w.fm.review = mapReview(p.reviewDecision);
          w.fm.merged = false;
        } else if (merged.has(pr)) {
          w.fm.merged = true;
          w.fm.state = "done";
        }
      }
      const owner = s(w, "owner");
      const session = owner && sessions?.find((x) => x.sessionId === owner);
      if (session) {
        w.fm.session_running = session.isRunning === true &&
          session.isArchived !== true;
        w.fm.session_last = toTs(session.lastActivityAt);
      }
      if (JSON.stringify(w.fm) !== before) {
        await writeWork(w, false);
        changed++;
      }
    }
    await commit(home, cfg, "scan");
  });
  console.log(
    `scan: ${prs.length} open PR(s), ${merged.size} merged, ${changed} work item(s) updated`,
  );
}

async function computeChanges(
  home: string,
  cfg: Config,
  since?: string,
): Promise<Change[]> {
  let ref = since ?? (await readText(join(home, ".swarm", "last-run")))?.trim();
  if (!ref) {
    ref = (await git(home, "rev-list", "--max-parents=0", "HEAD")).trim().split(
      "\n",
    )[0];
  }
  const ok = await run("git", [
    "-C",
    home,
    "rev-parse",
    "-q",
    "--verify",
    `${ref}^{commit}`,
  ]);
  if (ok.code !== 0) throw new Fail(`unknown ref ${ref}`);
  const nowMs = parseTs(now());
  const events: Change[] = [];
  for (const w of await listWork(home)) {
    const id = s(w, "id") || basename(w.path, ".md");
    const pr = s(w, "pr");
    const add = (kind: string, detail: string) =>
      events.push({ id, kind, detail, pr });
    const shown = await run("git", [
      "-C",
      home,
      "show",
      `${ref}:work/${basename(w.path)}`,
    ]);
    const old = shown.code === 0 ? parseWork(shown.stdout, w.path) : null;
    if (!old) add("new", `${s(w, "title")} (${s(w, "repo")})`);
    else {
      const was = (k: string) => s(old, k);
      const is = (k: string) => s(w, k);
      const sec = (x: Work, k: string) => x.sections.get(k) ?? "";
      if (was("state") === "queued" && is("state") !== "queued") {
        add(
          "started",
          `state=${is("state")}${is("owner") ? ` owner=${is("owner")}` : ""}`,
        );
      }
      const prOpened = !was("pr") && !!is("pr");
      if (prOpened) add("pr-opened", `state=${is("state")}`);
      if (was("ci") !== "failure" && is("ci") === "failure") {
        add("went-red", `ci=failure (was ${was("ci") || "none"})`);
      }
      // Only red -> green is news; pending -> success happens on every push.
      if (was("ci") === "failure" && is("ci") === "success") {
        add("went-green", "ci=success (was failure)");
      }
      const blocks = (t: string) => (t.match(/^### /gm) ?? []).length;
      if (sec(w, "Findings") && sec(w, "Findings") !== sec(old, "Findings")) {
        const n = blocks(sec(w, "Findings")) - blocks(sec(old, "Findings"));
        add(
          "new-findings",
          `${Math.max(n, 1)} new block(s); state=${is("state")}`,
        );
      }
      if (sec(w, "Question") && sec(w, "Question") !== sec(old, "Question")) {
        add("asked", firstLine(parseQuestion(sec(w, "Question")).text));
      }
      if (sec(w, "Answer") && sec(w, "Answer") !== sec(old, "Answer")) {
        add("answered", firstLine(sec(w, "Answer")));
      }
      if (is("state") === "blocked" && was("state") !== "blocked") {
        add("blocked", parseLog(sec(w, "Log")).at(-1)?.text ?? "");
      }
      if (is("state") === "ready" && was("state") !== "ready") {
        add("ready", "state=ready");
      }
      const wasMerged = old.fm.merged === true ||
        ["done", "archived"].includes(was("state"));
      if (!wasMerged && (w.fm.merged === true || is("state") === "done")) {
        add("merged", w.fm.merged === true ? "merged" : "state=done");
      }
      // A new head on an existing PR means a re-review may be due; pr-opened already covers the first one.
      if (is("pr") && !prOpened && is("head") && is("head") !== was("head")) {
        add("pushed", `head=${is("head")} (was ${was("head") || "none"})`);
      }
    }
    if (isStuck(w, cfg, nowMs)) {
      add("stuck", `state=${s(w, "state")}, last activity ${lastActivity(w)}`);
    }
    if (isUnanswered(w)) {
      add(
        "unanswered",
        firstLine(parseQuestion(w.sections.get("Question") ?? "").text),
      );
    }
  }
  return events;
}

function changeLine(c: Change): string {
  return `${c.id.padEnd(4)} ${c.kind.padEnd(12)} ${
    c.pr ? `${c.pr} ` : ""
  }${c.detail}`.trimEnd();
}

async function cmdChanges(ctx: Ctx) {
  const { home, flags } = ctx;
  const cfg = await readConfig(home);
  const events = await computeChanges(home, cfg, flags.since);
  if (flags.json) {
    console.log(
      JSON.stringify(
        events.map(({ id, kind, detail }) => ({ id, kind, detail })),
        null,
        2,
      ),
    );
  } else {
    for (const e of events) console.log(changeLine(e));
  }
  const failOn = (flags["fail-on"] ?? "").split(",").map((x) => x.trim())
    .filter(Boolean);
  if (events.some((e) => failOn.includes(e.kind))) throw new Fail("", 1);
}

function workJson(w: Work, nowMs: number, cfg: Config) {
  const q = w.sections.get("Question");
  const answer = w.sections.get("Answer");
  return {
    id: s(w, "id"),
    title: s(w, "title"),
    state: s(w, "state"),
    role: s(w, "role"),
    owner: s(w, "owner"),
    repo: s(w, "repo"),
    branch: s(w, "branch"),
    pr: s(w, "pr"),
    pr_url: prUrl(s(w, "pr")),
    head: s(w, "head"),
    verified_main: s(w, "verified_main"),
    ci: s(w, "ci") || "none",
    threads_open: Number(w.fm.threads_open ?? 0) || 0,
    review: s(w, "review") || "none",
    merged: w.fm.merged === true,
    needs: Array.isArray(w.fm.needs) ? w.fm.needs : [],
    created: s(w, "created"),
    updated: s(w, "updated"),
    session_running: w.fm.session_running === true,
    session_last: s(w, "session_last"),
    brief: w.sections.get("Brief") ?? "",
    log: parseLog(w.sections.get("Log") ?? ""),
    findings: w.sections.get("Findings") ?? "",
    question: q ? parseQuestion(q) : null,
    answer: answer ? answer : null,
    stuck: isStuck(w, cfg, nowMs),
  };
}

function parseDecisions(text: string) {
  const out: {
    id: string;
    ts: string;
    work: string;
    question: string;
    answer: string;
  }[] = [];
  for (const block of text.split(/^(?=## D\d+ )/m)) {
    const h = block.match(/^## (D\d+) \(([^)]*)\) (W\d+): ?(.*)$/m);
    if (!h) continue;
    const a = block.match(/^Answer: ?([\s\S]*)$/m);
    out.push({
      id: h[1],
      ts: h[2],
      work: h[3],
      question: h[4].trim(),
      answer: a ? a[1].trim() : "",
    });
  }
  return out;
}

function parseRuns(text: string) {
  return [...text.matchAll(/^- (\d{4}-\d\d-\d\d \d\d:\d\d)\s+(.*)$/gm)].map((
    m,
  ) => ({
    ts: m[1],
    summary: m[2].trim(),
  }));
}

async function buildState(home: string) {
  const cfg = await readConfig(home);
  const nowMs = parseTs(now());
  const items = await listWork(home);
  return {
    home,
    generated: now(),
    config: {
      next_id: cfg.next_id,
      stuck_hours: cfg.stuck_hours,
      owners: cfg.owners,
      repos: cfg.repos,
    },
    work: items.map((w) => workJson(w, nowMs, cfg)),
    changes: (await computeChanges(home, cfg)).map(({ id, kind, detail }) => ({
      id,
      kind,
      detail,
    })),
    decisions: parseDecisions(
      (await readText(join(home, "decisions.md"))) ?? "",
    ),
    runs: parseRuns((await readText(join(home, "runs.md"))) ?? ""),
  };
}

type State = Awaited<ReturnType<typeof buildState>>;

function table(work: State["work"]): string {
  const head = [
    "id",
    "state",
    "role",
    "repo",
    "pr",
    "ci",
    "threads",
    "owner",
    "updated",
  ];
  const rows = work.map((w) =>
    [
      w.id + (w.stuck ? "!" : ""),
      w.state,
      w.role,
      w.repo,
      w.pr,
      w.ci,
      String(w.threads_open),
      w.owner + (w.session_running ? "*" : ""),
      w.updated,
    ].map((c) => c || "-")
  );
  const widths = head.map((h, i) =>
    Math.max(h.length, ...rows.map((r) => r[i].length))
  );
  return [head, ...rows].map((r) =>
    r.map((c, i) => c.padEnd(widths[i])).join("  ").trimEnd()
  )
    .join("\n");
}

async function cmdStatus(ctx: Ctx) {
  const { home, flags } = ctx;
  const state = await buildState(home);
  if (flags.json) {
    console.log(JSON.stringify(state, null, 2));
    return;
  }
  if (!flags.overseer) {
    console.log(state.work.length ? table(state.work) : "no work items");
    return;
  }
  const counts = STATES.map((st) =>
    [st, state.work.filter((w) => w.state === st).length] as const
  )
    .filter(([, n]) => n > 0).map(([st, n]) => `${st} ${n}`);
  const out: string[] = [
    `swarm ${home} at ${state.generated}`,
    `States: ${counts.join(" · ") || "no work items"}`,
    "",
    "## Needs you",
  ];
  const open = state.work.filter((w) =>
    w.state === "needs-decision" && w.question && !w.answer
  );
  for (const w of open) {
    const q = w.question!;
    out.push(
      `${w.id}  ${w.title} (${w.repo}${w.pr ? ` ${w.pr}` : ""})`,
      `  ${q.text.replaceAll("\n", "\n  ")}`,
    );
    for (const o of q.options) out.push(`  - ${o.key}: ${o.text}`);
    if (q.recommended) out.push(`  Recommended: ${q.recommended}`);
    out.push(
      `  answer: ${invocation(home)} answer ${w.id} "${
        q.recommended || "<text>"
      }"`,
    );
  }
  if (!open.length) out.push("(nothing)");
  out.push("", "## Changes since last run");
  const cfg = await readConfig(home);
  const changes = await computeChanges(home, cfg);
  out.push(...(changes.length ? changes.map(changeLine) : ["(none)"]));
  out.push("", "## Work", state.work.length ? table(state.work) : "(none)");
  out.push("", "## Last runs");
  const runs = state.runs.slice(-3);
  out.push(
    ...(runs.length ? runs.map((r) => `- ${r.ts}  ${r.summary}`) : ["(none)"]),
  );
  console.log(out.join("\n"));
}

async function cmdReady(ctx: Ctx) {
  const { home, flags } = ctx;
  const id = normId(ctx.args[0]);
  const allowBehind = Number(flags["allow-behind"] ?? 0);
  if (!Number.isInteger(allowBehind) || allowBehind < 0) {
    throw new Fail("--allow-behind takes a whole number of commits");
  }
  await readConfig(home);
  const w = await readWork(home, id);
  const pr = s(w, "pr");
  const head = s(w, "head");
  const vm = s(w, "verified_main");
  const fails: string[] = [];
  if (!pr) fails.push("pr is not set");
  if (s(w, "ci") !== "success") {
    fails.push(`ci is ${s(w, "ci") || "none"}, not success`);
  }
  const threads = Number(w.fm.threads_open ?? 0);
  if (threads !== 0) fails.push(`${threads} unresolved review thread(s)`);
  if (s(w, "review") === "CHANGES_REQUESTED") {
    fails.push("review is CHANGES_REQUESTED");
  }
  if (!head) fails.push("head is not reported");
  if (!vm) fails.push("verified_main is not reported");
  if (pr) {
    const { repo, number } = splitPr(pr);
    const view = await gh([
      "pr",
      "view",
      number,
      "-R",
      repo,
      "--json",
      "headRefOid,body,baseRefName",
    ]);
    if (view.code !== 0) {
      fails.push(`gh pr view ${pr} failed: ${view.stderr.trim()}`);
    } else {
      const info = JSON.parse(view.stdout);
      const prHead = str(info.headRefOid);
      if (head && !prHead.startsWith(head)) {
        fails.push(`head ${head} is not the PR head ${prHead.slice(0, 7)}`);
      }
      if (head && !str(info.body).includes(`Verification at ${head}`)) {
        fails.push(`PR body does not contain "Verification at ${head}"`);
      }
      const base = str(info.baseRefName) || "main";
      if (vm) {
        const c = await gh([
          "api",
          `repos/${repo}/commits/${base}`,
          "--jq",
          ".sha",
        ]);
        const baseSha = c.stdout.trim();
        if (c.code !== 0 || !baseSha) {
          fails.push(`cannot read ${repo} ${base}: ${c.stderr.trim()}`);
        } else if (!baseSha.startsWith(vm)) {
          if (allowBehind > 0) {
            const cmp = await gh([
              "api",
              `repos/${repo}/compare/${vm}...${baseSha}`,
              "--jq",
              ".ahead_by",
            ]);
            const behind = Number(cmp.stdout.trim());
            if (
              cmp.code !== 0 || !Number.isFinite(behind) || behind > allowBehind
            ) {
              fails.push(
                `verified_main ${vm} is ${
                  cmp.code === 0 ? behind : "?"
                } commit(s) behind ${base} (allowed ${allowBehind})`,
              );
            }
          } else {fails.push(
              `verified_main ${vm} is not ${base} head ${baseSha.slice(0, 7)}`,
            );}
        }
      }
    }
  }
  if (fails.length) {
    console.log(`${id} is not ready:`);
    for (const f of fails) console.log(`- ${f}`);
    throw new Fail("", 1);
  }
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const fresh = await readWork(home, id);
    fresh.fm.state = "ready";
    addLog(
      fresh,
      whoFor(ctx, fresh, "overseer"),
      `ready: all checks passed at ${head}`,
    );
    await writeWork(fresh);
    await commit(home, cfg, `ready ${id}`);
  });
  console.log(`${id} ready`);
}

async function cmdSetState(ctx: Ctx, cmd: "done" | "archive") {
  const { home } = ctx;
  const id = normId(ctx.args[0]);
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const w = await readWork(home, id);
    if (cmd === "archive" && s(w, "state") !== "done") {
      throw new Fail(`${id} is ${s(w, "state")}; archive requires done`);
    }
    w.fm.state = cmd === "done" ? "done" : "archived";
    addLog(w, whoFor(ctx, w, "overseer"), `state=${w.fm.state}`);
    await writeWork(w);
    await commit(home, cfg, `${cmd} ${id}`);
  });
}

async function cmdRunDone(ctx: Ctx) {
  const { home } = ctx;
  const summary = oneLine(ctx.args.join(" "));
  if (!summary) throw new Fail(`usage: run-done "<summary>"`);
  await withLock(home, async () => {
    const cfg = await readConfig(home);
    const path = join(home, "runs.md");
    const text = (await readText(path)) ?? "# Runs\n";
    await Deno.writeTextFile(
      path,
      `${text.trimEnd()}\n- ${now()}  ${summary}\n`,
    );
    await commit(home, cfg, "run-done");
    // With auto_commit off this marks HEAD, so later changes are measured from the last commit.
    const sha = (await git(home, "rev-parse", "HEAD")).trim();
    await Deno.writeTextFile(join(home, ".swarm", "last-run"), `${sha}\n`);
    console.log(sha.slice(0, 7));
  });
}

async function cmdBoard(ctx: Ctx) {
  const dir = join(SKILL_DIR, "board");
  if (
    !(await exists(join(dir, "package.json"))) &&
    !(await exists(join(dir, "vite.config.ts")))
  ) {
    throw new Fail(`board not found: expected a Vite app in ${dir}`);
  }
  await readConfig(ctx.home);
  console.log(
    `board: starting Vite in ${dir} with SWARM_HOME=${ctx.home}; open the URL it prints (default http://localhost:5173)`,
  );
  const child = new Deno.Command(Deno.execPath(), {
    args: ["run", "-A", "npm:vite"],
    cwd: dir,
    env: { SWARM_HOME: ctx.home },
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  }).spawn();
  const status = await child.status;
  if (status.code !== 0) throw new Fail("", status.code);
}

// ---------- main ----------

const COMMANDS: Record<string, (ctx: Ctx) => Promise<void>> = {
  init: cmdInit,
  new: cmdNew,
  brief: cmdBrief,
  report: cmdReport,
  log: cmdLog,
  ask: cmdAsk,
  answer: cmdAnswer,
  findings: cmdFindings,
  scan: cmdScan,
  changes: cmdChanges,
  status: cmdStatus,
  ready: cmdReady,
  done: (ctx) => cmdSetState(ctx, "done"),
  archive: (ctx) => cmdSetState(ctx, "archive"),
  "run-done": cmdRunDone,
  board: cmdBoard,
};

export async function main(argv: string[]): Promise<number> {
  try {
    const parsed = parseArgs(argv, {
      string: [
        "home",
        "who",
        "role",
        "needs",
        "repo",
        "brief-file",
        "since",
        "sessions",
        "pr-status",
        "recommend",
        "fail-on",
        "allow-behind",
        "option",
      ],
      boolean: ["json", "overseer", "help"],
      collect: ["option"],
      alias: { h: "help" },
      unknown: (arg) => {
        if (arg.startsWith("-")) {
          throw new Fail(`unknown flag ${arg} (try help)`);
        }
        return true;
      },
    });
    const [cmd, ...args] = parsed._.map(String);
    if (parsed.help || !cmd || cmd === "help") {
      console.log(USAGE);
      return 0;
    }
    const run = COMMANDS[cmd];
    if (!run) throw new Fail(`unknown command "${cmd}" (try help)`);
    const home = resolve(
      parsed.home ?? Deno.env.get("SWARM_HOME") ?? DEFAULT_HOME,
    );
    await run({ home, flags: parsed as unknown as Flags, args });
    return 0;
  } catch (e) {
    if (!(e instanceof Fail)) throw e;
    if (e.message) console.error(`swarm: ${e.message}`);
    return e.code;
  }
}

if (import.meta.main) Deno.exit(await main(Deno.args));
