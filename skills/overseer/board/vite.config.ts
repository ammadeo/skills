import { defineConfig, type Plugin, type ViteDevServer } from "vite";
import react from "@vitejs/plugin-react";
import { execFile } from "node:child_process";
import { existsSync, type FSWatcher, readFileSync, watch } from "node:fs";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import type { IncomingMessage, ServerResponse } from "node:http";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import process from "node:process";

// Dev-server middleware for the board:
//   GET  /api/state   -> fixture, or `swarm status --json`
//   POST /api/answer  -> `swarm answer W<n> "<text>"`        { id, text }
//   POST /api/log     -> `swarm log W<n> "<text>"`           { id, text }
//   POST /api/new     -> `swarm new "<title>" --repo ...`    { title, repo, brief, role }
// plus a `swarm:update` HMR event when the swarm repo changes.
// With SWARM_STATE_FIXTURE set, writes return 409 and the command to run by hand.

type Json = Record<string, unknown>;

const ID = /^W\d+$/;
const REPO = /^[\w.-]+\/[\w.-]+$/;
const ROLES = new Set(["builder", "coordinator"]);

function readBody(req: IncomingMessage, limit = 256 * 1024): Promise<string> {
  return new Promise((ok, fail) => {
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (chunk: string) => {
      body += chunk;
      if (body.length > limit) {
        fail(new Error("body too large"));
        req.destroy();
      }
    });
    req.on("end", () => ok(body));
    req.on("error", fail);
  });
}

function shellQuote(s: string) {
  return `"${s.replace(/(["\\$`])/g, "\\$1")}"`;
}

function swarmState(): Plugin {
  const fixture = process.env.SWARM_STATE_FIXTURE ? resolve(process.env.SWARM_STATE_FIXTURE) : "";
  const rawHome = process.env.SWARM_HOME || join(homedir(), "swarm");
  const home = resolve(rawHome.replace(/^~(?=\/|$)/, homedir()));

  return {
    name: "swarm-state",
    configureServer(server: ViteDevServer) {
      const cli = resolve(server.config.root, "../scripts/swarm.ts");
      const log = server.config.logger;
      log.info(fixture ? `swarm: serving fixture ${fixture}` : `swarm: SWARM_HOME=${home}, cli=${cli}`);

      const run = (args: string[]) =>
        new Promise<{ code: number; stdout: string; stderr: string }>((ok) => {
          execFile(
            process.execPath, // the deno binary running vite
            ["run", "-A", cli, ...args, "--home", home],
            { cwd: dirname(cli), maxBuffer: 32 * 1024 * 1024, timeout: 30_000 },
            (err, stdout, stderr) => {
              ok({ code: err ? (typeof err.code === "number" ? err.code : 1) : 0, stdout, stderr });
            },
          );
        });

      server.middlewares.use("/api", async (req: IncomingMessage, res: ServerResponse) => {
        const send = (status: number, body: Json | string, type = "application/json") => {
          res.statusCode = status;
          res.setHeader("Content-Type", `${type}; charset=utf-8`);
          res.setHeader("Cache-Control", "no-store");
          res.end(typeof body === "string" ? body : JSON.stringify(body));
        };
        const route = (req.url ?? "").split("?")[0];

        if (route === "/state") {
          if (req.method !== "GET") return send(405, { error: "GET only" });
          if (fixture) {
            try {
              return send(200, readFileSync(fixture, "utf8"));
            } catch (e) {
              return send(500, { error: `cannot read SWARM_STATE_FIXTURE ${fixture}: ${(e as Error).message}` });
            }
          }
          if (!existsSync(cli)) return send(500, { error: `swarm CLI not found at ${cli}` });
          const r = await run(["status", "--json"]);
          if (r.code !== 0) {
            return send(500, { error: `swarm status --json --home ${home} failed (exit ${r.code})\n\n${r.stderr}` });
          }
          return send(200, r.stdout);
        }

        if (!["/answer", "/log", "/new"].includes(route)) return send(404, { error: `no route ${route}` });
        if (req.method !== "POST") return send(405, { error: "POST only" });

        let body: Json;
        try {
          body = JSON.parse(await readBody(req)) as Json;
        } catch (e) {
          return send(400, { error: `bad JSON body: ${(e as Error).message}` });
        }
        const str = (k: string) => (typeof body[k] === "string" ? (body[k] as string).trim() : "");

        // Build the CLI arguments (and the command the user could run instead).
        let args: string[];
        let cleanup = async () => {};
        if (route === "/new") {
          const title = str("title"), repo = str("repo"), brief = str("brief"), role = str("role") || "builder";
          if (!title) return send(400, { error: "title is required" });
          if (!REPO.test(repo)) return send(400, { error: "repo must look like owner/name" });
          if (!ROLES.has(role)) return send(400, { error: "role must be builder or coordinator" });
          args = ["new", title, "--repo", repo, "--role", role];
          if (brief) {
            const dir = await mkdtemp(join(tmpdir(), "swarm-brief-"));
            const file = join(dir, "brief.md");
            await writeFile(file, brief + "\n");
            args.push("--brief-file", file);
            cleanup = () => rm(dir, { recursive: true, force: true });
          }
        } else {
          const id = str("id"), text = str("text");
          if (!ID.test(id)) return send(400, { error: "id must be W<n>" });
          if (!text) return send(400, { error: "text is required" });
          args = [route.slice(1), id, text];
          if (route === "/log") args.push("--who", "user"); // notes from the board are the user's
        }
        const command = `swarm ${args.map((a) => (/^[\w./=:#-]+$/.test(a) ? a : shellQuote(a))).join(" ")}`;

        if (fixture) {
          await cleanup();
          return send(409, { error: "the board is serving a fixture; run this in a shell instead", command });
        }
        if (!existsSync(cli)) return send(500, { error: `swarm CLI not found at ${cli}`, command });
        const r = await run(args);
        await cleanup();
        log.info(`swarm: ${command} -> exit ${r.code}`, { timestamp: true });
        if (r.code !== 0) return send(r.code === 2 ? 400 : 500, { error: (r.stderr || r.stdout).trim(), command });
        return send(200, { ok: true, output: r.stdout.trim(), command });
      });

      // Watch directories (not files) so atomic rename-writes are still seen.
      let timer: ReturnType<typeof setTimeout> | undefined;
      const notify = (why: string) => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          log.info(`swarm:update (${why})`, { timestamp: true });
          server.ws.send({ type: "custom", event: "swarm:update" });
        }, 200);
      };
      const watchers: FSWatcher[] = [];
      const watchDir = (dir: string, accept: (file: string) => boolean) => {
        try {
          const w = watch(dir, (_event, file) => {
            const name = file ? basename(String(file)) : "";
            if (!name || accept(name)) notify(name ? join(dir, name) : dir);
          });
          w.on("error", (e) => log.warn(`swarm: watcher on ${dir} failed: ${e.message}`));
          watchers.push(w);
        } catch (e) {
          log.warn(`swarm: not watching ${dir}: ${(e as Error).message}`);
        }
      };
      if (fixture) {
        watchDir(dirname(fixture), (f) => f === basename(fixture));
      } else {
        watchDir(join(home, "work"), (f) => f.endsWith(".md"));
        watchDir(home, (f) => f === "decisions.md" || f === "runs.md" || f === "swarm.yml");
      }
      server.httpServer?.on("close", () => watchers.forEach((w) => w.close()));
    },
  };
}

export default defineConfig({ plugins: [react(), swarmState()] });
