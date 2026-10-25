<script lang="ts">
  import type { OpInfo } from "../lib/api";
  import { t, type Text } from "../lib/i18n.svelte";
  import { workspace } from "../lib/workspace.svelte";

  let { ops, onpick }: { ops: OpInfo[]; onpick: (op: OpInfo) => void } = $props();

  const CATEGORIES: Record<string, Text> = {
    pages: { tr: "Sayfalar", en: "Pages" },
    optimize: { tr: "Optimize et", en: "Optimise" },
    protect: { tr: "Koruma", en: "Protect" },
    stamp: { tr: "Damga ve numaralandırma", en: "Stamp & number" },
    convert: { tr: "Dönüştür", en: "Convert" },
  };

  let query = $state("");

  const groups = $derived.by(() => {
    const q = query.trim().toLocaleLowerCase();
    const out = new Map<string, OpInfo[]>();
    for (const op of ops) {
      if (op.category === "test") continue;
      const hay = `${op.title.tr} ${op.title.en} ${op.description.tr} ${op.description.en}`.toLocaleLowerCase();
      if (q && !hay.includes(q)) continue;
      const list = out.get(op.category) ?? [];
      list.push(op);
      out.set(op.category, list);
    }
    return [...out.entries()];
  });

  /** Why an operation can't run on the current selection, or null if it can. */
  function blocker(op: OpInfo): string | null {
    const sel = workspace.selected;
    if (!sel.length) return t("Önce dosya seçin", "Select files first");
    if (sel.some((e) => !op.accepts.includes(e.file!.kind))) {
      if (op.accepts.includes("pdf")) return t("Yalnızca PDF", "PDF only");
      if (op.accepts.includes("image")) return t("Yalnızca görsel", "Images only");
      return t("Yalnızca Word / Excel / PowerPoint", "Word / Excel / PowerPoint only");
    }
    if (sel.length < op.min_inputs) return t(`En az ${op.min_inputs} dosya`, `At least ${op.min_inputs} files`);
    if (sel.length > op.max_inputs)
      return op.max_inputs === 1 ? t("Tek dosya seçin", "Select one file") : t(`En çok ${op.max_inputs} dosya`, `At most ${op.max_inputs} files`);
    return null;
  }
</script>

<section class="tools" aria-label={t("Araçlar", "Tools")}>
  <input class="search" type="search" placeholder={t("Araç ara…", "Search tools…")} bind:value={query} />
  {#each groups as [cat, list] (cat)}
    <h3>{CATEGORIES[cat] ? t(CATEGORIES[cat]) : cat}</h3>
    <div class="grid">
      {#each list as op (op.name)}
        {@const why = blocker(op)}
        <button class="card" class:blocked={why} onclick={() => onpick(op)}>
          <strong>{t(op.title)}</strong>
          <span>{t(op.description)}</span>
          {#if why}<em>{why}</em>{/if}
        </button>
      {/each}
    </div>
  {:else}
    <p class="empty">{t("Eşleşen araç yok.", "No matching tools.")}</p>
  {/each}
</section>

<style>
  .tools {
    display: grid;
    gap: 10px;
    align-content: start;
  }
  .search {
    max-width: 360px;
  }
  h3 {
    margin: 14px 0 0;
    font-size: 0.8rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 10px;
  }
  .card {
    display: grid;
    gap: 6px;
    align-content: start;
    justify-content: stretch;
    justify-items: start;
    text-align: left;
    padding: 14px;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    transition:
      border-color 0.15s,
      transform 0.15s;
  }
  .card:hover {
    border-color: var(--accent);
    transform: translateY(-1px);
  }
  .card span {
    font-size: 0.85rem;
    color: var(--muted);
  }
  .card em {
    font-style: normal;
    font-size: 0.75rem;
    color: var(--warn);
  }
  .blocked strong {
    opacity: 0.75;
  }
  .empty {
    color: var(--muted);
  }
</style>
