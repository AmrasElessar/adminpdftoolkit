import { ApiError, deleteFile, type StoredFile, uploadFile } from "./api";

export interface Entry {
  key: string;
  name: string;
  size: number;
  status: "uploading" | "ready" | "error";
  progress: number;
  error?: string;
  file?: StoredFile;
  selected: boolean;
  password: string;
}

let seq = 0;

/** The files the user is working on, in their chosen order. */
class Workspace {
  entries = $state<Entry[]>([]);

  readonly selected = $derived(this.entries.filter((e) => e.selected && e.status === "ready"));

  add(files: Iterable<File>): void {
    for (const f of files) {
      const entry: Entry = {
        key: `u${++seq}`,
        name: f.name,
        size: f.size,
        status: "uploading",
        progress: 0,
        selected: true,
        password: "",
      };
      this.entries.push(entry);
      const live = this.entries[this.entries.length - 1]!; // the reactive proxy
      uploadFile(f, (p) => (live.progress = p))
        .then((stored) => {
          live.file = stored;
          live.name = stored.name;
          live.status = "ready";
        })
        .catch((e: unknown) => {
          live.status = "error";
          live.error = e instanceof ApiError ? e.message : String(e);
        });
    }
  }

  /** Put a job result into the workspace so it can feed the next tool. */
  adopt(file: StoredFile, select = true, password = ""): Entry {
    this.entries.push({
      key: `r${++seq}`,
      name: file.name,
      size: file.size,
      status: "ready",
      progress: 1,
      file,
      selected: select,
      password,
    });
    return this.entries[this.entries.length - 1]!;
  }

  remove(key: string): void {
    const i = this.entries.findIndex((e) => e.key === key);
    if (i < 0) return;
    const [e] = this.entries.splice(i, 1);
    if (e?.file) void deleteFile(e.file.id).catch(() => {});
  }

  move(from: number, to: number): void {
    if (from === to || from < 0 || to < 0 || from >= this.entries.length || to >= this.entries.length) return;
    const [e] = this.entries.splice(from, 1);
    this.entries.splice(to, 0, e!);
  }

  selectOnly(key: string): void {
    for (const e of this.entries) e.selected = e.key === key;
  }

  clear(): void {
    for (const e of [...this.entries]) this.remove(e.key);
  }
}

export const workspace = new Workspace();
