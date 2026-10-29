import { defineConfig, type Plugin, type ViteDevServer } from "vite";
import react from "@vitejs/plugin-react";
import { execFile } from "node:child_process";
import { existsSync, type FSWatcher, readFileSync, watch } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import process from "node:process";

// Serves GET /api/state (fixture or `swarm status --json`) and pushes a
// `swarm:update` HMR event when the swarm repo changes. Read-only.
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

      server.middlewares.use("/api/state", (req, res) => {
        const send = (status: number, type: string, body: string) => {
          res.statusCode = status;
          res.setHeader("Content-Type", `${type}; charset=utf-8`);
          res.setHeader("Cache-Control", "no-store");
          res.end(body);
        };
        const fail = (msg: string) => send(500, "text/plain", msg);
        if (req.method !== "GET") return send(405, "text/plain", "GET only");
        if (fixture) {
          try {
            return send(200, "application/json", readFileSync(fixture, "utf8"));
          } catch (e) {
            return fail(`cannot read SWARM_STATE_FIXTURE ${fixture}: ${(e as Error).message}`);
          }
        }
        if (!existsSync(cli)) return fail(`swarm CLI not found at ${cli}`);
        execFile(
          process.execPath, // the deno binary running vite
          ["run", "-A", cli, "status", "--json", "--home", home],
          { cwd: dirname(cli), maxBuffer: 32 * 1024 * 1024, timeout: 30_000 },
          (err, stdout, stderr) => {
            if (err) {
              return fail(`swarm status --json --home ${home} failed (exit ${err.code ?? "?"})\n\n${stderr || err.message}`);
            }
            send(200, "application/json", stdout);
          },
        );
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
        watchDir(home, (f) => f === "decisions.md" || f === "runs.md");
      }
      server.httpServer?.on("close", () => watchers.forEach((w) => w.close()));
    },
  };
}

export default defineConfig({ plugins: [react(), swarmState()] });
