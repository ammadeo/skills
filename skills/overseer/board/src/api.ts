// Thin client for the dev server's /api routes (see vite.config.ts).

export interface ApiResult {
  ok: boolean;
  status: number;
  error?: string;
  /** The equivalent `swarm …` command; present on every write, success or not. */
  command?: string;
  output?: string;
}

export async function post(route: "answer" | "log" | "new", body: Record<string, string>): Promise<ApiResult> {
  try {
    const res = await fetch(`/api/${route}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let data: Partial<ApiResult> = {};
    try {
      data = JSON.parse(text) as Partial<ApiResult>;
    } catch {
      data = { error: text || `HTTP ${res.status}` };
    }
    return { ok: res.ok, status: res.status, ...data };
  } catch (e) {
    return { ok: false, status: 0, error: e instanceof Error ? e.message : String(e) };
  }
}

/** Submit on Cmd/Ctrl+Enter. Plain Enter keeps its default (newline in a textarea). */
export function submitOnModEnter(e: React.KeyboardEvent<HTMLTextAreaElement>) {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    e.currentTarget.form?.requestSubmit();
  }
}
