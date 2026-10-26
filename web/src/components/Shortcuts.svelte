<script lang="ts">
  import { t } from "../lib/i18n.svelte";
  import { SHORTCUTS, ui } from "../lib/shortcuts.svelte";

  let dialog: HTMLDialogElement;
  $effect(() => {
    if (ui.showShortcuts && !dialog.open) dialog.showModal();
    else if (!ui.showShortcuts && dialog.open) dialog.close();
  });
</script>

<dialog bind:this={dialog} onclose={() => (ui.showShortcuts = false)} aria-labelledby="kb-title">
  <header>
    <h2 id="kb-title">{t("Klavye kısayolları", "Keyboard shortcuts")}</h2>
    <button class="icon" onclick={() => dialog.close()} aria-label={t("Kapat", "Close")}>✕</button>
  </header>
  <div class="cols">
    {#each SHORTCUTS as section (section.title.en)}
      <section>
        <h3>{t(section.title)}</h3>
        <dl>
          {#each section.items as item (item.label.en)}
            <div>
              <dt>{#each item.keys as k, i (i)}<kbd>{k}</kbd>{/each}</dt>
              <dd>{t(item.label)}</dd>
            </div>
          {/each}
        </dl>
      </section>
    {/each}
  </div>
  <p class="note">{t("macOS'ta Ctrl yerine ⌘ Cmd kullanılabilir.", "On macOS, ⌘ Cmd works in place of Ctrl.")}</p>
</dialog>

<style>
  dialog {
    width: min(1240px, calc(100vw - 32px));
    max-height: calc(100dvh - 48px);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text);
    padding: 18px 20px;
  }
  dialog::backdrop {
    background: rgb(0 0 0 / 0.4);
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  h2 {
    margin: 0;
    font-size: 1.15rem;
  }
  /* Up to four columns; long sections (the editor's) flow on into the next
     column row by row instead of forcing one tall column. */
  .cols {
    columns: 4 250px;
    column-gap: 28px;
    margin-top: 10px;
  }
  section {
    margin-bottom: 14px;
  }
  h3 {
    break-after: avoid;
    margin: 0 0 6px;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }
  dl {
    margin: 0;
    font-size: 0.85rem;
  }
  dl > div {
    display: grid;
    grid-template-columns: 8.5em 1fr;
    gap: 12px;
    align-items: center;
    padding: 2px 0;
    break-inside: avoid;
  }
  dt {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }
  dd {
    margin: 0;
  }
  kbd {
    min-width: 22px;
    padding: 1px 6px;
    border: 1px solid var(--border-strong);
    border-bottom-width: 2px;
    border-radius: 5px;
    background: var(--surface-2);
    font: 600 0.75rem/1.5 ui-monospace, monospace;
    text-align: center;
  }
  .note {
    margin: 4px 0 0;
    color: var(--muted);
    font-size: 0.8rem;
  }
</style>
