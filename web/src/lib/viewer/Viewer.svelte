<script lang="ts">
  import { onDestroy, untrack } from "svelte";
  import { fileUrl, JobFailed, runAndWait, type StoredFile } from "../api";
  import EditorOverlay from "../editor/EditorOverlay.svelte";
  import EditorToolbar from "../editor/EditorToolbar.svelte";
  import { EditorState, moved, TOOL_KEYS } from "../editor/model.svelte";
  import { typing, ui } from "../shortcuts.svelte";
  import { SpanCache } from "../editor/spans";
  import { t } from "../i18n.svelte";
  import type { Entry } from "../workspace.svelte";
  import KvkkOverlay from "../kvkk/KvkkOverlay.svelte";
  import KvkkPanel from "../kvkk/KvkkPanel.svelte";
  import { KvkkState } from "../kvkk/state.svelte";
  import Bookmarks from "./Bookmarks.svelte";
  import Organizer from "./Organizer.svelte";
  import PageView from "./PageView.svelte";
  import { openDocument, PasswordNeeded, type PDFDocumentProxy, type PDFPageProxy } from "./pdf";
  import { printDocument } from "./print";
  import { type Hit, Searcher } from "./search";

  type Mode = "view" | "organize" | "edit" | "kvkk";

  let {
    entry,
    initialMode = "view",
    onclose,
    onresult,
  }: {
    entry: Entry;
    initialMode?: Mode;
    onclose: () => void;
    /** A new version was saved; `password` still opens it (encryption is kept). */
    onresult: (file: StoredFile, mode: Mode, password: string) => void;
  } = $props();

  const file = untrack(() => entry.file!);
  let mode = $state<Mode>(untrack(() => initialMode));
  let doc = $state<PDFDocumentProxy | null>(null);
  let pages = $state<PDFPageProxy[]>([]);
  let error = $state("");
  let needPassword = $state(false);
  let passwordInput = $state(untrack(() => entry.password));
  let scale = $state(1);
  let current = $state(1);
  let scroller: HTMLDivElement | undefined = $state();
  let busy = $state("");
  let sidebar = $state<"pages" | "bookmarks">("pages");
  let notice = $state("");

  const editor = new EditorState();
  let kvkk = $state<KvkkState | null>(null);

  $effect(() => {
    if (mode !== "kvkk" || !doc || kvkk) return;
    const k = new KvkkState(file.id, entry.password);
    kvkk = k;
    void k.scan();
  });

  async function applyKvkk(): Promise<void> {
    if (!kvkk?.active.length) return;
    busy = t("KVKK işlemleri uygulanıyor…", "Applying personal-data treatments…");
    error = "";
    try {
      const job = await runAndWait("kvkk_apply", [{ id: file.id, password: entry.password || undefined }], {
        items: kvkk.payload(),
        remove_metadata: true,
        flatten: kvkk.flatten,
      });
      if (job.result) onresult(job.result, "view", entry.password);
    } catch (e) {
      error = e instanceof JobFailed && e.job.error ? t(e.job.error) : t("Uygulanamadı.", "Could not apply.");
    } finally {
      busy = "";
    }
  }
  let toolbar: ReturnType<typeof EditorToolbar> | undefined = $state();
  let spans = $state<SpanCache | null>(null);

  // ---- loading --------------------------------------------------------------
  async function load(password: string): Promise<void> {
    error = "";
    try {
      const d = await openDocument(file.id, password);
      entry.password = password;
      needPassword = false;
      doc = d;
      spans = new SpanCache(file.id, password);
      pages = await Promise.all(Array.from({ length: d.numPages }, (_, i) => d.getPage(i + 1)));
      fitWidth();
    } catch (e) {
      if (e instanceof PasswordNeeded) {
        needPassword = true;
        if (e.incorrect && password) error = t("Şifre yanlış.", "Wrong password.");
      } else error = t("PDF açılamadı.", "Could not open the PDF.");
    }
  }
  void load(untrack(() => entry.password));

  onDestroy(() => {
    void doc?.loadingTask.destroy();
  });

  // ---- zoom & navigation -----------------------------------------------------
  function fitWidth(): void {
    const first = pages[0];
    if (!first || !scroller) return;
    const vp = first.getViewport({ scale: 1 });
    scale = Math.max(0.25, Math.min(4, (scroller.clientWidth - 48) / vp.width));
  }

  function zoom(factor: number): void {
    scale = Math.max(0.25, Math.min(5, Math.round(scale * factor * 100) / 100));
  }

  function goTo(n: number): void {
    const el = scroller?.querySelector<HTMLElement>(`.page[data-page="${n}"]`);
    el?.scrollIntoView({ block: "start" });
    current = n;
  }

  function onScroll(): void {
    if (!scroller) return;
    const mid = scroller.scrollTop + scroller.clientHeight / 3;
    for (const el of scroller.querySelectorAll<HTMLElement>(".page")) {
      if (el.offsetTop + el.offsetHeight > mid) {
        current = Number(el.dataset.page);
        break;
      }
    }
  }

  // ---- search -------------------------------------------------------------------
  let query = $state("");
  let hits = $state<Hit[]>([]);
  let hitIndex = $state(-1);
  let searchAbort: AbortController | null = null;

  async function search(): Promise<void> {
    if (!doc) return;
    searchAbort?.abort();
    searchAbort = new AbortController();
    hits = await new Searcher(doc).find(query, searchAbort.signal);
    hitIndex = hits.length ? 0 : -1;
    if (hits[0]) goTo(hits[0].page);
  }

  function step(delta: number): void {
    if (!hits.length) return;
    hitIndex = (hitIndex + delta + hits.length) % hits.length;
    const h = hits[hitIndex]!;
    if (h.page !== current) goTo(h.page);
  }

  function pageHits(n: number): number[] {
    return hits.filter((h) => h.page === n).flatMap((h) => h.items);
  }
  function currentItem(n: number): number {
    const h = hits[hitIndex];
    return h && h.page === n ? (h.items[0] ?? -1) : -1;
  }

  // ---- actions -------------------------------------------------------------------
  async function print(): Promise<void> {
    if (!doc) return;
    busy = t("Yazdırmaya hazırlanıyor…", "Preparing to print…");
    try {
      await printDocument(doc, (f) => (busy = `${t("Yazdırmaya hazırlanıyor", "Preparing to print")} ${Math.round(f * 100)}%`));
    } finally {
      busy = "";
    }
  }

  // Scanned documents have no text layer; offer OCR like Acrobat does.
  let scanned = $state(false);
  $effect(() => {
    const d = doc;
    if (!d) return;
    void (async () => {
      const sample = Math.min(d.numPages, 3);
      let chars = 0;
      for (let n = 1; n <= sample; n++) {
        const content = await (await d.getPage(n)).getTextContent();
        for (const it of content.items) if ("str" in it) chars += it.str.trim().length;
      }
      scanned = chars === 0;
    })();
  });

  async function runOcr(): Promise<void> {
    if (editor.count && !confirm(t("Kaydedilmemiş düzenlemeler silinecek. Devam edilsin mi?", "Unsaved edits will be lost. Continue?"))) return;
    busy = t("Metin tanınıyor (OCR)… büyük belgelerde birkaç dakika sürebilir.", "Recognising text (OCR)… large documents can take a few minutes.");
    error = "";
    try {
      const job = await runAndWait(
        "ocr",
        [{ id: file.id, password: entry.password || undefined }],
        { languages: "tur+eng", mode: "skip" },
        (j) => {
          if (j.status === "running") busy = `${t("Metin tanınıyor (OCR)", "Recognising text (OCR)")} ${Math.round(j.progress * 100)}%`;
        },
      );
      editor.clear();
      if (job.result) onresult(job.result, mode === "kvkk" ? "kvkk" : "edit", entry.password);
    } catch (e) {
      error = e instanceof JobFailed && e.job.error ? t(e.job.error) : t("OCR başarısız oldu.", "OCR failed.");
    } finally {
      busy = "";
    }
  }

  async function saveOrganize(plan: { page: number; rotate: number }[]): Promise<void> {
    busy = t("Sayfalar uygulanıyor…", "Applying pages…");
    try {
      const job = await runAndWait("organize", [{ id: file.id, password: entry.password || undefined }], { plan });
      if (job.result) onresult(job.result, "organize", entry.password);
    } catch (e) {
      error = e instanceof JobFailed && e.job.error ? t(e.job.error) : t("Kaydedilemedi.", "Could not save.");
    } finally {
      busy = "";
    }
  }

  async function saveEdits(): Promise<void> {
    if (!editor.count) return;
    busy = t("Düzenlemeler kaydediliyor…", "Saving edits…");
    error = "";
    try {
      const operations = editor.toOperations();
      const fields = editor.toFieldSpecs();
      let current: StoredFile = file;
      const password = entry.password;
      if (operations.length) {
        const job = await runAndWait("edit", [{ id: current.id, password: password || undefined }], { operations });
        const failed = (job.data?.failed ?? []) as { index: number }[];
        if (failed.length) notice = t(`${failed.length} düzenleme uygulanamadı.`, `${failed.length} edits could not be applied.`);
        if (job.result) current = job.result; // saving keeps the encryption, so the password still applies
      }
      if (fields.length) {
        const job = await runAndWait("form_create", [{ id: current.id, password: password || undefined }], { fields });
        if (job.result) current = job.result;
      }
      editor.clear();
      if (current.id !== file.id) onresult(current, "edit", password);
    } catch (e) {
      error = e instanceof JobFailed && e.job.error ? t(e.job.error) : t("Kaydedilemedi.", "Could not save.");
    } finally {
      busy = "";
    }
  }

  function close(): void {
    if (editor.count && !confirm(t("Kaydedilmemiş düzenlemeler silinecek. Çıkılsın mı?", "Unsaved edits will be lost. Leave?"))) return;
    onclose();
  }

  function switchMode(next: Mode): void {
    if (mode === "edit" && editor.count && next !== "edit") {
      if (!confirm(t("Kaydedilmemiş düzenlemeler silinecek. Devam edilsin mi?", "Unsaved edits will be lost. Continue?"))) return;
      editor.clear();
    }
    mode = next;
  }

  $effect(() => {
    if (!editor.count) return;
    const guard = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  });

  function keydown(e: KeyboardEvent): void {
    if (typing(e) || ui.showShortcuts) return;
    const mod = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();
    if (e.altKey && ["1", "2", "3", "4"].includes(e.key)) {
      e.preventDefault();
      switchMode((["view", "organize", "edit", "kvkk"] as const)[Number(e.key) - 1]!);
      return;
    }
    if (mode === "kvkk" && mod && key === "s") {
      e.preventDefault();
      void applyKvkk();
      return;
    }
    if (mod && key === "f") {
      e.preventDefault();
      document.getElementById("viewer-search")?.focus();
      return;
    }
    if (mod && key === "p") return void (e.preventDefault(), print());
    if (mod && (e.key === "+" || e.key === "=")) return void (e.preventDefault(), zoom(1.15));
    if (mod && e.key === "-") return void (e.preventDefault(), zoom(1 / 1.15));
    if (mod && e.key === "0") return void (e.preventDefault(), fitWidth());
    if (doc && mode !== "organize" && !mod) {
      if (e.key === "PageDown") return void (e.preventDefault(), goTo(Math.min(doc.numPages, current + 1)));
      if (e.key === "PageUp") return void (e.preventDefault(), goTo(Math.max(1, current - 1)));
      if (e.key === "Home" && !editor.selected) return void (e.preventDefault(), goTo(1));
      if (e.key === "End" && !editor.selected) return void (e.preventDefault(), goTo(doc.numPages));
    }
    if (mode !== "edit") {
      if (e.key === "Escape") close();
      return;
    }
    if (mod && key === "s") {
      e.preventDefault();
      void saveEdits();
    } else if (mod && key === "z") {
      e.preventDefault();
      if (e.shiftKey) editor.redo();
      else editor.undo();
    } else if (mod && key === "y") {
      e.preventDefault();
      editor.redo();
    } else if ((e.key === "Delete" || e.key === "Backspace") && editor.selectedId) {
      e.preventDefault();
      editor.remove(editor.selectedId);
    } else if (e.key === "Escape") {
      editor.selectedId = null;
      editor.tool = "select";
    } else if (e.key.startsWith("Arrow") && editor.selected) {
      e.preventDefault();
      const d = e.shiftKey ? 10 : 1;
      const dx = e.key === "ArrowLeft" ? -d : e.key === "ArrowRight" ? d : 0;
      const dy = e.key === "ArrowUp" ? d : e.key === "ArrowDown" ? -d : 0;
      editor.update(editor.selected.id, moved(editor.selected, dx, dy));
    } else if (!mod && !e.altKey && TOOL_KEYS[key]) {
      e.preventDefault();
      toolbar?.choose(TOOL_KEYS[key]!);
    }
  }
</script>

<svelte:window onkeydown={keydown} />

<section class="viewer" aria-label={file.name}>
  <header class="bar">
    <button class="ghost" onclick={close} aria-label={t("Kapat", "Close")}>←</button>
    <strong class="name" title={file.name}>{file.name}</strong>
    <div class="modes" role="tablist" aria-label={t("Mod", "Mode")}>
      <button role="tab" aria-selected={mode === "view"} class:on={mode === "view"} onclick={() => switchMode("view")}>{t("Görüntüle", "View")}</button>
      <button role="tab" aria-selected={mode === "organize"} class:on={mode === "organize"} onclick={() => switchMode("organize")}>{t("Sayfalar", "Pages")}</button>
      <button role="tab" aria-selected={mode === "edit"} class:on={mode === "edit"} onclick={() => switchMode("edit")}>{t("Düzenle", "Edit")}</button>
      <button role="tab" aria-selected={mode === "kvkk"} class:on={mode === "kvkk"} onclick={() => switchMode("kvkk")} title="Alt+4">KVKK</button>
    </div>
    {#if mode !== "organize" && doc}
      <div class="group">
        <button class="small ghost" onclick={() => zoom(1 / 1.15)} aria-label={t("Uzaklaştır", "Zoom out")}>−</button>
        <button class="small ghost zoom" onclick={fitWidth} title={t("Genişliğe sığdır", "Fit width")}>{Math.round(scale * 100)}%</button>
        <button class="small ghost" onclick={() => zoom(1.15)} aria-label={t("Yakınlaştır", "Zoom in")}>+</button>
      </div>
      <div class="group">
        <input
          class="pageno"
          type="number"
          min="1"
          max={doc.numPages}
          value={current}
          aria-label={t("Sayfa", "Page")}
          onchange={(e) => goTo(Math.max(1, Math.min(doc!.numPages, Number(e.currentTarget.value) || 1)))}
        />
        <span class="muted">/ {doc.numPages}</span>
      </div>
      <form
        class="group search"
        onsubmit={(e) => {
          e.preventDefault();
          if (hits.length && query) step(1);
          else void search();
        }}
      >
        <input id="viewer-search" type="search" placeholder={t("Ara…", "Search…")} bind:value={query} oninput={() => (hits = [])} />
        {#if hits.length}<span class="muted">{hitIndex + 1}/{hits.length}</span>
          <button type="button" class="small ghost" onclick={() => step(-1)} aria-label={t("Önceki", "Previous")}>↑</button>
          <button type="button" class="small ghost" onclick={() => step(1)} aria-label={t("Sonraki", "Next")}>↓</button>
        {:else if query && hitIndex === -1 && hits.length === 0}
          <button type="submit" class="small ghost">{t("Bul", "Find")}</button>
        {/if}
      </form>
    {/if}
    <div class="group end">
      <button class="small ghost" onclick={print} disabled={!doc || !!busy}>{t("Yazdır", "Print")}</button>
      <a class="button small ghost" href={fileUrl(file.id)} download={file.name}>{t("İndir", "Download")}</a>
    </div>
  </header>

  {#if mode === "edit" && doc}
    <EditorToolbar bind:this={toolbar} {editor} saving={!!busy} onsave={saveEdits} />
    {#if scanned}
      <p class="status scan" role="status">
        {t(
          "Bu belge taranmış görünüyor: metinler görsel olduğu için doğrudan düzenlenemez. OCR ile tanındığında metni değiştirebilirsiniz.",
          "This document looks scanned: its text is an image and can't be edited directly. Recognise it with OCR to change the text.",
        )}
        <button class="primary small" onclick={runOcr} disabled={!!busy}>{t("OCR uygula", "Run OCR")}</button>
      </p>
    {/if}
  {/if}
  {#if busy}<p class="status" aria-live="polite">{busy}</p>{/if}
  {#if notice}<p class="status warn" role="status">{notice} <button class="small ghost" onclick={() => (notice = "")}>✕</button></p>{/if}
  {#if error && !needPassword}<p class="status error" role="alert">{error}</p>{/if}

  {#if needPassword}
    <form
      class="password"
      onsubmit={(e) => {
        e.preventDefault();
        void load(passwordInput);
      }}
    >
      <h2>{t("Bu PDF şifreli", "This PDF is password-protected")}</h2>
      <input type="password" bind:value={passwordInput} aria-label={t("Şifre", "Password")} autocomplete="off" />
      {#if error}<p class="error">{error}</p>{/if}
      <button class="primary" type="submit">{t("Aç", "Open")}</button>
    </form>
  {:else if mode === "organize" && pages.length}
    <div class="organize-wrap">
      <Organizer {pages} busy={!!busy} onsave={saveOrganize} />
    </div>
  {:else}
    <div class="body">
      {#if mode === "kvkk" && kvkk}
        <aside class="thumbs kvkk-side" aria-label={t("KVKK bulguları", "Personal-data findings")}>
          <KvkkPanel {kvkk} busy={!!busy} ongo={goTo} onapply={applyKvkk} {scanned} onocr={runOcr} />
        </aside>
      {:else}
      <nav class="thumbs" aria-label={t("Kenar çubuğu", "Sidebar")}>
        <div class="side-tabs" role="tablist" aria-label={t("Kenar çubuğu", "Sidebar")}>
          <button role="tab" aria-selected={sidebar === "pages"} class:on={sidebar === "pages"} onclick={() => (sidebar = "pages")}>{t("Sayfalar", "Pages")}</button>
          <button role="tab" aria-selected={sidebar === "bookmarks"} class:on={sidebar === "bookmarks"} onclick={() => (sidebar = "bookmarks")}>{t("Yer imleri", "Bookmarks")}</button>
        </div>
        {#if sidebar === "bookmarks" && doc}
          <Bookmarks
            fileId={file.id}
            password={entry.password}
            pageCount={doc.numPages}
            {current}
            ongo={goTo}
            onsaved={(f) => onresult(f, mode, entry.password)}
          />
        {:else}
          {#each pages as p (p.pageNumber)}
            <button class="thumb" class:on={current === p.pageNumber} onclick={() => goTo(p.pageNumber)} aria-label={`${t("Sayfa", "Page")} ${p.pageNumber}`}>
              <PageView page={p} scale={110 / p.getViewport({ scale: 1 }).width} textLayer={false} />
              <span>{p.pageNumber}</span>
            </button>
          {/each}
        {/if}
      </nav>
      {/if}
      <!-- svelte-ignore a11y_no_noninteractive_tabindex (scroll region must be keyboard-scrollable, WCAG 2.1.1) -->
      <div
        class="pages"
        bind:this={scroller}
        onscroll={onScroll}
        class:editing={mode === "edit"}
        tabindex="0"
        role="region"
        aria-label={t("Belge sayfaları", "Document pages")}
      >
        {#each pages as p (p.pageNumber)}
          <PageView page={p} {scale} textLayer={mode === "view"} hits={pageHits(p.pageNumber)} current={currentItem(p.pageNumber)}>
            {#snippet overlay(viewport)}
              {#if mode === "edit" && spans}
                <EditorOverlay page={p.pageNumber} {viewport} {editor} {spans} onocr={runOcr} />
              {:else if mode === "kvkk" && kvkk}
                <KvkkOverlay page={p.pageNumber} {viewport} {kvkk} />
              {/if}
            {/snippet}
          </PageView>
        {/each}
      </div>
    </div>
  {/if}
</section>

<style>
  .viewer {
    display: flex;
    flex-direction: column;
    gap: 10px;
    height: calc(100dvh - 92px);
    min-height: 420px;
  }
  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    align-items: center;
    padding: 8px 10px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .name {
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .modes {
    display: flex;
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .modes button {
    border: 0;
    border-radius: 0;
    min-height: 34px;
    background: transparent;
  }
  .modes button.on {
    background: var(--accent);
    color: var(--on-accent);
  }
  .group {
    display: flex;
    gap: 4px;
    align-items: center;
  }
  .group.end {
    margin-left: auto;
  }
  .zoom {
    min-width: 62px;
    font-variant-numeric: tabular-nums;
  }
  .pageno {
    width: 64px !important;
    padding: 4px 6px !important;
  }
  .search input {
    width: 180px;
    padding: 5px 8px;
  }
  .muted {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .status {
    margin: 0;
    padding: 6px 12px;
    border-radius: 8px;
    background: var(--surface);
    border: 1px solid var(--border);
  }
  .status.scan {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
    background: var(--accent-soft);
  }
  .status.warn {
    color: var(--warn);
  }
  .status.error,
  .error {
    color: var(--danger);
  }
  .body {
    flex: 1;
    min-height: 0;
    display: flex;
    gap: 10px;
  }
  .thumbs.kvkk-side {
    width: 340px;
  }
  .side-tabs {
    display: flex;
    gap: 2px;
    position: sticky;
    top: -6px;
    z-index: 1;
    background: var(--surface);
    padding-bottom: 4px;
  }
  .side-tabs button {
    flex: 1;
    min-height: 28px;
    padding: 2px 4px;
    font-size: 0.75rem;
    border-color: transparent;
  }
  .side-tabs button.on {
    background: var(--accent-soft);
    color: var(--accent);
  }
  .thumbs {
    width: 190px;
    flex: none;
    overflow-y: auto;
    display: grid;
    align-content: start;
    /* Buttons carry a min-height, which lets "auto" rows shrink below their
       content once the sidebar overflows; pin rows to content height. */
    grid-auto-rows: max-content;
    gap: 10px;
    padding: 6px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .thumb {
    display: grid;
    justify-items: center;
    gap: 4px;
    padding: 6px;
    border: 2px solid transparent;
    background: transparent;
    font-size: 0.75rem;
  }
  .thumb.on {
    border-color: var(--accent);
  }
  .thumb :global(.page) {
    pointer-events: none;
  }
  .pages {
    flex: 1;
    min-width: 0;
    overflow: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 16px;
    background: var(--surface-2);
    border-radius: var(--radius);
  }
  .organize-wrap {
    flex: 1;
    min-height: 0;
    overflow: auto;
  }
  .password {
    display: grid;
    gap: 10px;
    width: min(360px, 100%);
    margin: 40px auto;
    padding: 24px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .password h2 {
    margin: 0;
    font-size: 1.1rem;
  }
  @media (max-width: 600px) {
    .modes {
      flex: 1 1 100%;
      overflow-x: auto;
    }
    .modes button {
      flex: 1 0 auto;
      padding: 6px 10px;
    }
    .name {
      max-width: calc(100vw - 120px);
    }
  }
  @media (max-width: 760px) {
    /* Page thumbnails go; the KVKK findings become a sheet under the pages,
       so personal data can be treated from a phone too. */
    .thumbs:not(.kvkk-side) {
      display: none;
    }
    .body {
      flex-direction: column;
    }
    .thumbs.kvkk-side {
      order: 2;
      width: auto;
      max-height: 45dvh;
    }
    .pages {
      flex: 1;
      min-height: 200px;
    }
    .viewer {
      height: calc(100dvh - 76px);
    }
  }
</style>
