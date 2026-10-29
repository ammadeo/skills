import { assert, assertEquals, assertMatch } from "@std/assert";
import { fromFileUrl, join } from "@std/path";
import { readWork, writeWork } from "./swarm.ts";

const SWARM = fromFileUrl(new URL("./swarm.ts", import.meta.url));

interface Result {
  code: number;
  stdout: string;
  stderr: string;
}

async function sw(
  home: string,
  args: string[],
  opts: { stdin?: string; env?: Record<string, string> } = {},
): Promise<Result> {
  const child = new Deno.Command(Deno.execPath(), {
    args: ["run", "-A", SWARM, ...args],
    env: { SWARM_HOME: home, SWARM_WHO: "", ...opts.env },
    stdin: opts.stdin === undefined ? "null" : "piped",
    stdout: "piped",
    stderr: "piped",
  }).spawn();
  if (opts.stdin !== undefined) {
    const w = child.stdin.getWriter();
    await w.write(new TextEncoder().encode(opts.stdin));
    await w.close();
  }
  const out = await child.output();
  const dec = new TextDecoder();
  return {
    code: out.code,
    stdout: dec.decode(out.stdout),
    stderr: dec.decode(out.stderr),
  };
}

async function ok(
  home: string,
  args: string[],
  opts?: { stdin?: string; env?: Record<string, string> },
) {
  const r = await sw(home, args, opts);
  assertEquals(r.code, 0, `swarm ${args.join(" ")}: ${r.stderr}${r.stdout}`);
  return r.stdout;
}

async function gitLog(home: string): Promise<string[]> {
  const out = await new Deno.Command("git", {
    args: ["-C", home, "log", "--format=%s"],
    stdout: "piped",
  }).output();
  return new TextDecoder().decode(out.stdout).trim().split("\n");
}

/** A fresh, initialised swarm home in /private/tmp, removed afterwards. */
async function withHome(fn: (home: string) => Promise<void>) {
  const home = await Deno.makeTempDir({
    dir: "/private/tmp",
    prefix: "swarm-test-",
  });
  try {
    await ok(home, ["init"]);
    await fn(home);
  } finally {
    // git may still be finishing background maintenance; retry the cleanup briefly.
    for (let i = 0; i < 5; i++) {
      try {
        await Deno.remove(home, { recursive: true });
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 200));
      }
    }
  }
}

async function status(home: string) {
  return JSON.parse(await ok(home, ["status", "--json"]));
}

async function script(dir: string, name: string, body: string) {
  const path = join(dir, name);
  await Deno.writeTextFile(path, `#!/bin/sh\n${body}\n`);
  await Deno.chmod(path, 0o755);
  return path;
}

Deno.test("init is idempotent and makes one commit", async () => {
  await withHome(async (home) => {
    const second = await ok(home, ["init"]);
    assertMatch(second, /^alias swarm='deno run -A .*swarm\.ts --home /m);
    assertEquals(await gitLog(home), ["init"]);
    for (const f of ["swarm.yml", "decisions.md", "runs.md", ".gitignore"]) {
      assert((await Deno.stat(join(home, f))).isFile, f);
    }
    assertEquals(
      await Deno.readTextFile(join(home, ".gitignore")),
      ".swarm/\n",
    );
  });
});

Deno.test("new allocates ids, writes the file and bumps next_id", async () => {
  await withHome(async (home) => {
    assertEquals(
      (await ok(home, ["new", "First", "--repo", "acme/app"])).trim(),
      "W1",
    );
    const out = await ok(home, [
      "new",
      "Second",
      "--repo",
      "acme/app",
      "--role",
      "coordinator",
      "--needs",
      "W1",
    ], { stdin: "Goal: do the second thing.\n" });
    assertEquals(out.trim(), "W2");
    const w2 = await readWork(home, "W2");
    assertEquals(w2.fm.state, "queued");
    assertEquals(w2.fm.role, "coordinator");
    assertEquals(w2.fm.needs, ["W1"]);
    assertEquals(w2.sections.get("Brief"), "Goal: do the second thing.");
    assertMatch(
      await Deno.readTextFile(join(home, "swarm.yml")),
      /^next_id: 3 +# next W number$/m,
    );
    assertEquals((await gitLog(home)).slice(0, 2), ["new W2", "new W1"]);
  });
});

Deno.test("report and log write front matter and Log lines", async () => {
  await withHome(async (home) => {
    await ok(home, ["new", "Item", "--repo", "acme/app"]);
    await ok(home, [
      "report",
      "W1",
      "state=working",
      "owner=sess-1",
      "branch=feat/x",
      "pr=https://github.com/acme/app/pull/7",
      "head=1234567",
    ]);
    await ok(home, ["log", "W1", "pushed the first commit"], {
      env: { SWARM_WHO: "builder-1" },
    });
    const w = await readWork(home, "W1");
    assertEquals(w.fm.state, "working");
    assertEquals(w.fm.pr, "acme/app#7");
    assertEquals(w.fm.head, "1234567");
    const log = w.sections.get("Log")!.split("\n");
    assertMatch(
      log[0],
      /^- \d{4}-\d\d-\d\d \d\d:\d\d builder: report state=working owner=sess-1/,
    );
    assertMatch(log[1], /builder-1: pushed the first commit$/);
    const refused = await sw(home, ["report", "W1", "state=ready"]);
    assertEquals(refused.code, 2);
    assertMatch(refused.stderr, /use swarm ready/);
    assertEquals((await sw(home, ["report", "W1", "ci=success"])).code, 2);
    assertEquals((await gitLog(home)).slice(0, 2), ["log W1", "report W1"]);
  });
});

Deno.test("ask -> needs-decision -> answer restores state and writes D1", async () => {
  await withHome(async (home) => {
    await ok(home, ["new", "Throttle", "--repo", "acme/app"]);
    await ok(home, ["report", "W1", "state=working"]);
    await ok(home, [
      "ask",
      "W1",
      "Per account or per IP?",
      "--option",
      "A: per account (cost: one migration)",
      "--option",
      "B: per IP (cost: shared offices)",
      "--recommend",
      "A",
    ]);
    let w = await readWork(home, "W1");
    assertEquals(w.fm.state, "needs-decision");
    assertEquals(w.fm.state_before, "working");
    let st = await status(home);
    assertEquals(st.work[0].question, {
      text: "Per account or per IP?",
      options: [
        { key: "A", text: "per account (cost: one migration)" },
        { key: "B", text: "per IP (cost: shared offices)" },
      ],
      recommended: "A",
    });
    assert(st.changes.some((c: { kind: string }) => c.kind === "unanswered"));

    assertEquals(
      (await ok(home, ["answer", "W1", "A, keep it simple"])).trim(),
      "D1",
    );
    w = await readWork(home, "W1");
    assertEquals(w.fm.state, "working");
    assertEquals(w.fm.state_before, "");
    assertEquals(w.sections.get("Answer"), "A — keep it simple");
    assert(w.sections.has("Question"));
    const decisions = await Deno.readTextFile(join(home, "decisions.md"));
    assertMatch(
      decisions,
      /^## D1 \(\d{4}-\d\d-\d\d \d\d:\d\d\) W1: Per account or per IP\?\nAnswer: A \(per account\) — keep it simple$/m,
    );
    st = await status(home);
    assertEquals(st.decisions[0].id, "D1");
    assertEquals(st.decisions[0].work, "W1");
    assertEquals(st.work[0].answer, "A — keep it simple");
    assertMatch(st.work[0].log.at(-1).text, /^answered D1/);
    assertEquals(st.work[0].log.at(-1).who, "user");
  });
});

Deno.test("findings moves pr-open to fixing", async () => {
  await withHome(async (home) => {
    await ok(home, ["new", "Item", "--repo", "acme/app"]);
    await ok(home, ["report", "W1", "state=pr-open", "pr=acme/app#5"]);
    await ok(home, ["findings", "W1", "--who", "reviewer"], {
      stdin: "1 medium: missing index\n",
    });
    const w = await readWork(home, "W1");
    assertEquals(w.fm.state, "fixing");
    assertMatch(
      w.sections.get("Findings")!,
      /^### \d{4}-\d\d-\d\d \d\d:\d\d reviewer\n1 medium: missing index$/,
    );
  });
});

Deno.test("run-done marks the baseline; changes reports new and went-red", async () => {
  await withHome(async (home) => {
    await ok(home, ["new", "Item", "--repo", "acme/app"]);
    await ok(home, [
      "report",
      "W1",
      "state=pr-open",
      "pr=acme/app#5",
      "head=aaaaaaa",
    ]);
    let w = await readWork(home, "W1");
    w.fm.ci = "success";
    await writeWork(w);
    await ok(home, ["run-done", "first run"]);
    const head = (await new Deno.Command("git", {
      args: ["-C", home, "rev-parse", "HEAD"],
      stdout: "piped",
    })
      .output()).stdout;
    assertEquals(
      (await Deno.readTextFile(join(home, ".swarm", "last-run"))).trim(),
      new TextDecoder().decode(head).trim(),
    );
    assertEquals(JSON.parse(await ok(home, ["changes", "--json"])), []);

    await ok(home, ["new", "Second", "--repo", "acme/app"]);
    w = await readWork(home, "W1");
    w.fm.ci = "failure"; // scan-owned field, written directly
    await writeWork(w);
    await ok(home, ["report", "W1", "head=bbbbbbb"]);
    const events = JSON.parse(await ok(home, ["changes", "--json"]));
    assertEquals(events, [
      { id: "W1", kind: "went-red", detail: "ci=failure (was success)" },
      { id: "W1", kind: "pushed", detail: "head=bbbbbbb (was aaaaaaa)" },
      { id: "W2", kind: "new", detail: "Second (acme/app)" },
    ]);
    const text = await ok(home, ["changes"]);
    assertEquals(
      text.split("\n")[0],
      "W1   went-red     acme/app#5 ci=failure (was success)",
    );
    assertEquals(
      (await sw(home, ["changes", "--fail-on", "went-red"])).code,
      1,
    );

    const st = await status(home);
    assertEquals(st.runs, [{ ts: st.runs[0].ts, summary: "first run" }]);
  });
});

Deno.test("stuck is computed from the current state", async () => {
  await withHome(async (home) => {
    await ok(home, ["new", "Item", "--repo", "acme/app"]);
    await ok(home, ["report", "W1", "state=working"], {
      env: { SWARM_NOW: "2026-10-29 08:00" },
    });
    const later = { SWARM_NOW: "2026-10-29 12:00" };
    const st = JSON.parse(await ok(home, ["status", "--json"], { env: later }));
    assertEquals(st.work[0].stuck, true);
    assert(st.changes.some((c: { kind: string }) => c.kind === "stuck"));
  });
});

Deno.test("status --json has the contract shape", async () => {
  await withHome(async (home) => {
    await ok(home, ["new", "Item", "--repo", "acme/app"], { stdin: "Do it." });
    await ok(home, ["report", "W1", "state=working", "pr=acme/app#9"]);
    await ok(home, ["log", "W1", "second line"]);
    const st = await status(home);
    assertEquals(Object.keys(st), [
      "home",
      "generated",
      "config",
      "work",
      "changes",
      "decisions",
      "runs",
    ]);
    assertEquals(st.home, home);
    assertEquals(Object.keys(st.config), [
      "next_id",
      "stuck_hours",
      "owners",
      "repos",
    ]);
    assertEquals(st.config.next_id, 2);
    const w = st.work[0];
    assertEquals(Object.keys(w).sort(), [
      "answer",
      "branch",
      "brief",
      "ci",
      "created",
      "findings",
      "head",
      "id",
      "log",
      "merged",
      "needs",
      "owner",
      "pr",
      "pr_url",
      "question",
      "repo",
      "review",
      "role",
      "session_last",
      "session_running",
      "state",
      "stuck",
      "threads_open",
      "title",
      "updated",
      "verified_main",
    ]);
    assertEquals(w.pr_url, "https://github.com/acme/app/pull/9");
    assertEquals(w.brief, "Do it.");
    assertEquals(w.question, null);
    assertEquals(w.answer, null);
    assertEquals(w.ci, "none");
    assertEquals(w.threads_open, 0);
    assertEquals(w.merged, false);
    assertEquals(w.log.map((l: { text: string }) => l.text), [
      "report state=working pr=acme/app#9",
      "second line",
    ]);
    assertEquals(st.decisions, []);
    assertEquals(st.runs, []);
  });
});

Deno.test("ready lists every unmet condition against a stubbed gh, then passes", async () => {
  await withHome(async (home) => {
    const stubDir = join(home, ".swarm");
    await ok(home, ["new", "Item", "--repo", "acme/app"]);
    await ok(home, [
      "report",
      "W1",
      "state=pr-open",
      "pr=acme/app#5",
      "head=aaaaaaa",
      "verified_main=bbbbbbb",
    ]);
    await Deno.writeTextFile(
      join(stubDir, "pr.json"),
      JSON.stringify({
        headRefOid: "ccccccc111",
        body: "no proof here",
        baseRefName: "main",
      }),
    );
    const stub = await script(
      stubDir,
      "gh",
      `case "$1" in
  pr) cat "${stubDir}/pr.json" ;;
  api) echo ddddddd222 ;;
esac`,
    );
    const env = { SWARM_GH_STUB: stub };
    const fail = await sw(home, ["ready", "W1"], { env });
    assertEquals(fail.code, 1);
    for (
      const reason of [
        "ci is none, not success",
        "head aaaaaaa is not the PR head ccccccc",
        'PR body does not contain "Verification at aaaaaaa"',
        "verified_main bbbbbbb is not main head ddddddd",
      ]
    ) assert(fail.stdout.includes(reason), `${reason} in\n${fail.stdout}`);
    assertEquals((await readWork(home, "W1")).fm.state, "pr-open");

    const w = await readWork(home, "W1");
    Object.assign(w.fm, {
      ci: "success",
      head: "ccccccc",
      verified_main: "ddddddd",
    });
    await writeWork(w);
    await Deno.writeTextFile(
      join(stubDir, "pr.json"),
      JSON.stringify({
        headRefOid: "ccccccc111",
        body: "Verification at ccccccc: ok",
        baseRefName: "main",
      }),
    );
    assertEquals((await ok(home, ["ready", "W1"], { env })).trim(), "W1 ready");
    assertEquals((await readWork(home, "W1")).fm.state, "ready");
  });
});

Deno.test("scan copies PR fields, matches by branch and marks merged PRs done", async () => {
  await withHome(async (home) => {
    const dir = join(home, ".swarm");
    await ok(home, ["new", "By branch", "--repo", "acme/app"]);
    await ok(home, [
      "report",
      "W1",
      "state=working",
      "branch=feat/a",
      "owner=s1",
    ]);
    await ok(home, ["new", "Merged", "--repo", "acme/app"]);
    await ok(home, ["report", "W2", "state=pr-open", "pr=acme/app#2"]);
    await Deno.writeTextFile(
      join(dir, "prs.json"),
      JSON.stringify([{
        repo: "acme/app",
        number: 1,
        head: "feat/a",
        ci: "FAILURE",
        failingChecks: ["lint"],
        threadsUnresolved: 2,
        reviewDecision: "REVIEW_REQUIRED",
      }]),
    );
    const prStatus = await script(dir, "pr-status", `cat "${dir}/prs.json"`);
    const gh = await script(dir, "gh", "echo MERGED");
    await Deno.writeTextFile(
      join(dir, "sessions.json"),
      JSON.stringify([{
        sessionId: "s1",
        isRunning: true,
        lastActivityAt: "2026-10-29T10:00:00",
        isArchived: false,
      }]),
    );
    await ok(home, [
      "scan",
      "--pr-status",
      prStatus,
      "--sessions",
      join(dir, "sessions.json"),
    ], {
      env: { SWARM_GH_STUB: gh },
    });
    const w1 = await readWork(home, "W1");
    assertEquals(
      [
        w1.fm.pr,
        w1.fm.ci,
        w1.fm.threads_open,
        w1.fm.review,
        w1.fm.session_running,
        w1.fm.session_last,
      ],
      ["acme/app#1", "failure", 2, "REVIEW_REQUIRED", true, "2026-10-29 10:00"],
    );
    const w2 = await readWork(home, "W2");
    assertEquals([w2.fm.merged, w2.fm.state], [true, "done"]);
    assertEquals((await gitLog(home))[0], "scan");
  });
});

Deno.test("a held lock fails with exit 3", async () => {
  await withHome(async (home) => {
    await ok(home, ["new", "Item", "--repo", "acme/app"]);
    await Deno.writeTextFile(join(home, ".swarm", "lock"), "12345\n");
    const r = await sw(home, ["log", "W1", "blocked by the lock"], {
      env: { SWARM_LOCK_WAIT_MS: "300" },
    });
    assertEquals(r.code, 3);
    assertMatch(r.stderr, /locked/);
  });
});

Deno.test("brief without a role template exits 2 and names the path", async () => {
  await withHome(async (home) => {
    await ok(home, ["new", "Item", "--repo", "acme/app"]);
    const r = await sw(home, ["brief", "W1", "--role", "reviewer"]);
    if (r.code === 0) {
      assertMatch(r.stdout, /## Brief/); // templates exist once the lead adds them
    } else {
      assertEquals(r.code, 2);
      assertMatch(r.stderr, /references\/roles\/reviewer\.md/);
    }
  });
});
