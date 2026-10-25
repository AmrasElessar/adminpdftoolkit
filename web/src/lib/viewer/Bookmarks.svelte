<script lang="ts">
  import { JobFailed, runAndWait, type StoredFile } from "../api";
  import { t } from "../i18n.svelte";

  interface Item {
    key: number;
    level: number;
    title: string;
    page: number;
  }

  let {
    fileId,
    password,
    pageCount,
    current,
    ongo,
    onsaved,
  }: {
    fileId: string;
    password: string;
    pageCount: number;
    current: number;
    ongo: (page: number) => void;
    onsaved: (file: StoredFile) => void;
  } = $props();

  let seq = 0;
  let items = $state<Item[]>([]);
  let original = "";
  let loading = $state(true);
  let saving = $state(false);
  let error = $state("");
  let selected = $state<number | null>(null);

  const dirty = $derived(JSON.stringify(items.map(({ level, title, page }) => [level, title, page])) !== original);

  async function load(): Promise<void> {
    try {
      const job = await runAndWait("get_outline", [{ id: fileId, password: password || undefined }], {});
      const raw = (job.data?.items ?? []) as { level: number; title: string; page: number }[];
      items = raw.map((r) => ({ key: ++seq, level: r.level, title: r.title, page: Math.max(1, r.page) }));
      original = JSON.stringify(items.map(({ level, title, page }) => [level, title, page]));
    } catch {
      error = t("Yer imleri okunamadı.", "Could not read bookmarks.");
    } finally {
      loading = false;
    }
  }
  void load();

  const index = $derived(items.findIndex((i) => i.key === selected));

  function add(): void {
    const at = index >= 0 ? index + 1 : items.length;
    const level = index >= 0 ? items[index]!.level : 1;
    const item = { key: ++seq, level, title: `${t("Sayfa", "Page")} ${current}`, page: current };
    items.splice(at, 0, item);
    selected = item.key;
  }

  function remove(): void {
    if (index < 0) return;
    items.splice(index, 1);
    selected = null;
  }

  function indent(delta: 1 | -1): void {
    if (index < 0) return;
    const it = items[index]!;
    const max = index === 0 ? 1 : items[index - 1]!.level + 1;
    it.level = Math.max(1, Math.min(max, it.level + delta));
  }

  function move(delta: 1 | -1): void {
    const j = index + delta;
    if (index < 0 || j < 0 || j >= items.length) return;
    [items[index], items[j]] = [items[j]!, items[index]!];
  }

  /** Levels may only step down one at a time; repair before saving. */
  function normalised(): { level: number; title: string; page: number }[] {
    let prev = 0;
    return items.map((i) => {
      const level = Math.min(i.level, prev + 1);
      prev = level;
      return { level, title: i.title.trim() || "—", page: Math.max(1, Math.min(pageCount, i.page)) };
    });
  }

  async function save(): Promise<void> {
    saving = true;
    error = "";
    try {
      const job = await runAndWait("set_outline", [{ id: fileId, password: password || undefined }], { items: normalised() });
      if (job.result) onsaved(job.result);
    } catch (e) {
      error = e instanceof JobFailed && e.job.error ? t(e.job.error) : t("Kaydedilemedi.", "Could not save.");
    } finally {
      saving = false;
    }
  }
</script>

<div class="bookmarks">
  <div class="bar">
    <button class="icon" onclick={add} title={t("Bu sayfaya yer imi ekle", "Bookmark this page")} aria-label={t("Ekle", "Add")}>＋</button>
    <button class="icon" onclick={remove} disabled={index < 0} aria-label={t("Sil", "Delete")}>✕</button>
    <button class="icon" onclick={() => indent(-1)} disabled={index < 0} aria-label={t("Üst düzeye al", "Outdent")}>⇤</button>
    <button class="icon" onclick={() => indent(1)} disabled={index < 0} aria-label={t("Alt düzeye al", "Indent")}>⇥</button>
    <button class="icon" onclick={() => move(-1)} disabled={index <= 0} aria-label={t("Yukarı", "Up")}>↑</button>
    <button class="icon" onclick={() => move(1)} disabled={index < 0 || index >= items.length - 1} aria-label={t("Aşağı", "Down")}>↓</button>
  </div>
  {#if loading}
    <p class="muted">{t("Yükleniyor…", "Loading…")}</p>
  {:else if !items.length}
    <p class="muted">{t("Yer imi yok. ＋ ile geçerli sayfayı ekleyin.", "No bookmarks. Use ＋ to add the current page.")}</p>
  {/if}
  <ol>
    {#each items as it (it.key)}
      <li class:on={selected === it.key} style:padding-left={`${(it.level - 1) * 12 + 4}px`}>
        <input
          class="title"
          value={it.title}
          maxlength="300"
          aria-label={t("Başlık", "Title")}
          onfocus={() => (selected = it.key)}
          oninput={(e) => (it.title = e.currentTarget.value)}
        />
        <button class="page" onclick={() => { selected = it.key; ongo(it.page); }} title={t("Git", "Go")}>{it.page}</button>
      </li>
    {/each}
  </ol>
  {#if error}<p class="error">{error}</p>{/if}
  {#if dirty}
    <button class="primary small" disabled={saving} onclick={save}>{saving ? t("Kaydediliyor…", "Saving…") : t("Yer imlerini kaydet", "Save bookmarks")}</button>
  {/if}
</div>

<style>
  .bookmarks {
    display: grid;
    gap: 6px;
    align-content: start;
  }
  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  li {
    display: flex;
    gap: 4px;
    align-items: center;
    border-radius: 6px;
  }
  li.on {
    background: var(--accent-soft);
  }
  .title {
    flex: 1;
    min-width: 0;
    padding: 3px 6px !important;
    font-size: 0.8rem;
    border-color: transparent !important;
    background: transparent !important;
  }
  .title:focus {
    border-color: var(--border-strong) !important;
    background: var(--surface) !important;
  }
  .page {
    min-height: 24px;
    padding: 0 6px;
    font-size: 0.75rem;
    border-color: transparent;
    color: var(--muted);
  }
  .muted {
    color: var(--muted);
    font-size: 0.8rem;
    margin: 0;
  }
  .error {
    color: var(--danger);
    font-size: 0.8rem;
    margin: 0;
  }
</style>
