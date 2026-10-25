<script lang="ts">
  import { formatBytes, t } from "../lib/i18n.svelte";
  import { workspace } from "../lib/workspace.svelte";

  let { maxUploadMb }: { maxUploadMb: number } = $props();

  let picker: HTMLInputElement;
  let dragOver = $state(false);
  let dragIndex = $state<number | null>(null);

  function onDrop(e: DragEvent): void {
    e.preventDefault();
    dragOver = false;
    if (e.dataTransfer?.files.length) workspace.add(e.dataTransfer.files);
  }

  function onPick(): void {
    if (picker.files) workspace.add(picker.files);
    picker.value = "";
  }

  function rowDrop(e: DragEvent, to: number): void {
    e.preventDefault();
    e.stopPropagation();
    if (dragIndex !== null) workspace.move(dragIndex, to);
    dragIndex = null;
  }

  const icon: Record<string, string> = { pdf: "PDF", image: "IMG", docx: "DOC", xlsx: "XLS", pptx: "PPT" };
</script>

<section
  class="tray"
  class:over={dragOver}
  aria-label={t("Dosyalar", "Files")}
  ondragover={(e) => {
    if (dragIndex === null) {
      e.preventDefault();
      dragOver = true;
    }
  }}
  ondragleave={() => (dragOver = false)}
  ondrop={onDrop}
>
  <header>
    <h2>{t("Dosyalar", "Files")}</h2>
    {#if workspace.entries.length}
      <button class="ghost small" onclick={() => workspace.clear()}>{t("Temizle", "Clear")}</button>
    {/if}
  </header>

  <button class="drop" onclick={() => picker.click()}>
    <strong>{t("Dosya seçin veya buraya bırakın", "Choose files or drop them here")}</strong>
    <span>PDF, JPG, PNG, TIFF, WebP · {t("en fazla", "up to")} {maxUploadMb} MB</span>
  </button>
  <input bind:this={picker} type="file" multiple hidden onchange={onPick} />

  {#if workspace.entries.length}
    <ol class="list">
      {#each workspace.entries as e, i (e.key)}
        <li
          class:dragging={dragIndex === i}
          class:failed={e.status === "error"}
          draggable={e.status === "ready"}
          ondragstart={() => (dragIndex = i)}
          ondragend={() => (dragIndex = null)}
          ondragover={(ev) => ev.preventDefault()}
          ondrop={(ev) => rowDrop(ev, i)}
        >
          <input
            type="checkbox"
            aria-label={t("Seç", "Select")}
            disabled={e.status !== "ready"}
            bind:checked={e.selected}
          />
          <span class="badge" data-kind={e.file?.kind ?? "other"}>{icon[e.file?.kind ?? ""] ?? "…"}</span>
          <div class="info">
            <span class="name" title={e.name}>{e.name}</span>
            <span class="meta">
              {#if e.status === "uploading"}
                {t("Yükleniyor", "Uploading")} {Math.round(e.progress * 100)}%
              {:else if e.status === "error"}
                {e.error}
              {:else}
                {formatBytes(e.size)}{#if e.file?.pages}{" · "}{e.file.pages}
                  {t("sayfa", e.file.pages === 1 ? "page" : "pages")}{/if}
              {/if}
            </span>
            {#if e.file?.encrypted}
              <input
                class="password"
                type="password"
                autocomplete="off"
                placeholder={t("PDF şifresi", "PDF password")}
                aria-label={t("PDF şifresi", "PDF password")}
                bind:value={e.password}
              />
            {/if}
            {#if e.status === "uploading"}
              <progress max="1" value={e.progress}></progress>
            {/if}
          </div>
          <div class="actions">
            <button class="icon" aria-label={t("Yukarı taşı", "Move up")} disabled={i === 0} onclick={() => workspace.move(i, i - 1)}>↑</button>
            <button
              class="icon"
              aria-label={t("Aşağı taşı", "Move down")}
              disabled={i === workspace.entries.length - 1}
              onclick={() => workspace.move(i, i + 1)}>↓</button
            >
            <button class="icon" aria-label={t("Kaldır", "Remove")} onclick={() => workspace.remove(e.key)}>✕</button>
          </div>
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .tray {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--border);
    min-height: 0;
  }
  .tray.over {
    outline: 2px dashed var(--accent);
    outline-offset: -6px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  h2 {
    margin: 0;
    font-size: 1rem;
  }
  .drop {
    display: grid;
    gap: 4px;
    padding: 22px 12px;
    border: 1.5px dashed var(--border-strong);
    border-radius: var(--radius);
    background: var(--surface-2);
    color: var(--text);
    text-align: center;
  }
  .drop span {
    font-size: 0.8rem;
    color: var(--muted);
  }
  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 6px;
    overflow: auto;
  }
  li {
    display: grid;
    grid-template-columns: auto auto 1fr auto;
    gap: 10px;
    align-items: center;
    padding: 8px 10px;
    border-radius: 10px;
    background: var(--surface-2);
    border: 1px solid transparent;
  }
  li[draggable="true"] {
    cursor: grab;
  }
  li.dragging {
    opacity: 0.4;
  }
  li.failed {
    border-color: var(--danger);
  }
  .badge {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 4px 6px;
    border-radius: 6px;
    background: var(--accent-soft);
    color: var(--accent);
  }
  .badge[data-kind="image"] {
    background: var(--ok-soft);
    color: var(--ok);
  }
  .info {
    display: grid;
    gap: 2px;
    min-width: 0;
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 550;
  }
  .meta {
    font-size: 0.78rem;
    color: var(--muted);
  }
  .failed .meta {
    color: var(--danger);
  }
  .password {
    margin-top: 4px;
    padding: 4px 8px;
    font-size: 0.85rem;
  }
  progress {
    width: 100%;
    height: 4px;
  }
  .actions {
    display: flex;
    gap: 2px;
  }
</style>
