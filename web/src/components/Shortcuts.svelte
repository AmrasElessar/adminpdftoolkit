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
            <dt>{#each item.keys as k, i (i)}<kbd>{k}</kbd>{/each}</dt>
            <dd>{t(item.label)}</dd>
          {/each}
        </dl>
      </section>
    {/each}
  </div>
  <p class="note">{t("macOS'ta Ctrl yerine ⌘ Cmd kullanılabilir.", "On macOS, ⌘ Cmd works in place of Ctrl.")}</p>
</dialog>

<style>
  dialog {
    width: min(920px, calc(100vw - 32px));
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
  .cols {
    columns: 260px;
    column-gap: 24px;
    margin-top: 10px;
  }
  section {
    break-inside: avoid;
    margin-bottom: 14px;
  }
  h3 {
    margin: 0 0 6px;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }
  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 5px 12px;
    margin: 0;
    font-size: 0.85rem;
  }
  dt {
    display: flex;
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
