import type { Text } from "./i18n.svelte";

export type FileKind = "pdf" | "image" | "docx" | "xlsx" | "pptx" | "other";

export interface StoredFile {
  id: string;
  name: string;
  size: number;
  kind: FileKind;
  mime: string;
  pages: number | null;
  encrypted: boolean;
}

export interface Session {
  version: string;
  csrf: string;
  local: boolean;
  paired: boolean;
  lan_enabled: boolean;
  max_upload_mb: number;
}

export interface JsonSchema {
  type?: string;
  title?: string;
  title_tr?: string;
  title_en?: string;
  help_tr?: string;
  help_en?: string;
  default?: unknown;
  enum?: (string | number)[];
  const?: string | number;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  ui?: {
    widget?: "password" | "color" | "range";
    step?: number;
    options?: Record<string, Text>;
    show_if?: Record<string, unknown>;
  };
  properties?: Record<string, JsonSchema>;
  required?: string[];
}

export interface OpInfo {
  name: string;
  category: string;
  title: Text;
  description: Text;
  accepts: FileKind[];
  min_inputs: number;
  max_inputs: number;
  schema: JsonSchema;
}

export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export interface Job {
  id: string;
  op: string;
  status: JobStatus;
  progress: number;
  message: string;
  error: Text | null;
  outputs: StoredFile[];
  result: StoredFile | null;
}

/** An error with a message already fit for the user. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

let csrf = "";

async function parseError(res: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = (await res.json()).detail;
  } catch {
    detail = res.statusText;
  }
  // FastAPI validation errors arrive as an array; flatten for display.
  if (Array.isArray(detail)) {
    const fields: Record<string, string> = {};
    for (const e of detail as { field?: string; loc?: unknown[]; message?: string; msg?: string }[]) {
      const key = e.field ?? (e.loc ?? []).slice(1).join(".");
      fields[key] = e.message ?? e.msg ?? "invalid";
    }
    return new ApiError(res.status, Object.entries(fields).map(([k, v]) => `${k}: ${v}`).join("; "), fields);
  }
  return new ApiError(res.status, typeof detail === "string" ? detail : `HTTP ${res.status}`);
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "network");
  }
  if (!res.ok) throw await parseError(res);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export async function loadSession(): Promise<Session> {
  const s = await request<Session>("GET", "/api/session");
  csrf = s.csrf;
  return s;
}

export const pair = (key: string) => request<{ paired: boolean }>("POST", "/api/session/pair", { key });
export const listOps = () => request<OpInfo[]>("GET", "/api/ops");
export const deleteFile = (id: string) => request<void>("DELETE", `/api/files/${encodeURIComponent(id)}`);
export const getJob = (id: string) => request<Job>("GET", `/api/jobs/${encodeURIComponent(id)}`);
export const cancelJob = (id: string) => request<Job>("POST", `/api/jobs/${encodeURIComponent(id)}/cancel`);

export function runOp(
  name: string,
  inputs: { id: string; password?: string }[],
  params: Record<string, unknown>,
): Promise<Job> {
  return request<Job>("POST", `/api/ops/${encodeURIComponent(name)}`, { inputs, params });
}

export function fileUrl(id: string, inline = false): string {
  return `/api/files/${encodeURIComponent(id)}${inline ? "?inline=1" : ""}`;
}

/** Upload with progress. XHR because fetch() cannot report upload progress. */
export function uploadFile(file: File, onProgress: (fraction: number) => void): Promise<StoredFile> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", "/api/files");
    xhr.setRequestHeader("X-CSRF-Token", csrf);
    xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status === 201) {
        resolve(JSON.parse(xhr.responseText) as StoredFile);
        return;
      }
      let msg = `HTTP ${xhr.status}`;
      try {
        msg = JSON.parse(xhr.responseText).detail ?? msg;
      } catch {
        // keep status text
      }
      reject(new ApiError(xhr.status, msg));
    };
    xhr.onerror = () => reject(new ApiError(0, "network"));
    xhr.send(file);
  });
}

const TERMINAL: JobStatus[] = ["done", "failed", "cancelled"];

/**
 * Follow a job until it finishes. Uses SSE (cookies authenticate it, so it
 * works for paired LAN clients too) and falls back to polling.
 * Returns a function that stops watching.
 */
export function watchJob(id: string, onUpdate: (job: Job) => void): () => void {
  let stopped = false;
  let source: EventSource | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const poll = async () => {
    if (stopped) return;
    try {
      const job = await getJob(id);
      onUpdate(job);
      if (TERMINAL.includes(job.status)) return;
    } catch {
      // transient; retry
    }
    timer = setTimeout(poll, 700);
  };

  if (typeof EventSource !== "undefined") {
    source = new EventSource(`/api/jobs/${encodeURIComponent(id)}/events`);
    source.onmessage = (e) => {
      const job = JSON.parse(e.data) as Job;
      onUpdate(job);
      if (TERMINAL.includes(job.status)) source?.close();
    };
    source.onerror = () => {
      source?.close();
      source = null;
      void poll();
    };
  } else {
    void poll();
  }

  return () => {
    stopped = true;
    source?.close();
    clearTimeout(timer);
  };
}
