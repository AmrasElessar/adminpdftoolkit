<script lang="ts">
  import type { OpInfo } from "../lib/api";
  import { t, type Text } from "../lib/i18n.svelte";
  import { workspace } from "../lib/workspace.svelte";

  let {
    ops,
    onpick,
    onopen,
  }: { ops: OpInfo[]; onpick: (op: OpInfo) => void; onopen: (mode: "view" | "organize" | "edit") => void } = $props();

  const CATEGORIES: { id: string; icon: string; label: Text }[] = [
    { id: "pages", icon: "📑", label: { tr: "Sayfalar", en: "Pages" } },
    { id: "convert", icon: "🔄", label: { tr: "Dönüştür", en: "Convert" } },
    { id: "ocr", icon: "🔍", label: { tr: "OCR", en: "OCR" } },
    { id: "extract", icon: "📤", label: { tr: "Çıkar", en: "Extract" } },
    { id: "optimize", icon: "⚡", label: { tr: "Optimize et", en: "Optimise" } },
    { id: "stamp", icon: "🏷", label: { tr: "Damga ve numara", en: "Stamp & number" } },
    { id: "forms", icon: "🧾", label: { tr: "Formlar", en: "Forms" } },
    { id: "sign", icon: "✒", label: { tr: "İmza", en: "Sign" } },
    { id: "protect", icon: "🔒", label: { tr: "Koruma", en: "Protect" } },
    { id: "redact", icon: "⬛", label: { tr: "Karartma (KVKK)", en: "Redact" } },
    { id: "security", icon: "🛡", label: { tr: "Güvenlik", en: "Security" } },
    { id: "compare", icon: "⚖", label: { tr: "Karşılaştır", en: "Compare" } },
    { id: "document", icon: "🗂", label: { tr: "Belge yapısı", en: "Document" } },
    { id: "archive", icon: "🏛", label: { tr: "Arşiv", en: "Archive" } },
    { id: "inspect", icon: "ℹ", label: { tr: "İncele", en: "Inspect" } },
    { id: "workflow", icon: "📊", label: { tr: "İş akışları", en: "Workflows" } },
  ];

  const FEATURED = [
    { mode: "edit" as const, icon: "✎", tr: "PDF Düzenle", en: "Edit PDF", dtr: "Metni değiştirin; metin, görsel, şekil, imza, not ve form alanı ekleyin.", den: "Change text; add text, images, shapes, signatures, notes and form fields." },
    { mode: "organize" as const, icon: "▦", tr: "Sayfaları Düzenle", en: "Organize Pages", dtr: "Küçük resimleri sürükleyerek sıralayın, döndürün, silin, boş sayfa ekleyin.", den: "Drag thumbnails to reorder, rotate, delete or insert blank pages." },
    { mode: "view" as const, icon: "👁", tr: "Görüntüle ve Ara", en: "View & Search", dtr: "PDF'i okuyun, içinde arayın, yer imlerini düzenleyin, yazdırın.", den: "Read, search inside, edit bookmarks and print the PDF." },
  ];

  let query = $state("");
  let tip = $state<{ title: string; body: string; why: string | null; x: number; y: number; above: boolean } | null>(null);

  const single = $derived(workspace.selected.length === 1 && workspace.selected[0]!.file!.kind === "pdf");

  const groups = $derived.by(() => {
    const q = query.trim().toLocaleLowerCase("tr");
    const byCat = new Map<string, OpInfo[]>();
    for (const op of ops) {
      if (op.category === "test" || op.hidden || op.category === "edit") continue;
      const hay = `${op.title.tr} ${op.title.en} ${op.description.tr} ${op.description.en}`.toLocaleLowerCase("tr");
      if (q && !hay.includes(q)) continue;
      byCat.set(op.category, [...(byCat.get(op.category) ?? []), op]);
    }
    const known = CATEGORIES.filter((c) => byCat.has(c.id)).map((c) => ({ ...c, ops: byCat.get(c.id)! }));
    const extra = [...byCat.keys()]
      .filter((k) => !CATEGORIES.some((c) => c.id === k))
      .map((k) => ({ id: k, icon: "•", label: { tr: k, en: k }, ops: byCat.get(k)! }));
    return [...known, ...extra];
  });

  /** Why an operation can't run on the current selection, or null if it can. */
  function blocker(op: OpInfo): string | null {
    const sel = workspace.selected;
    if (op.max_inputs === 0) return null;
    if (!sel.length) return t("Önce soldan dosya seçin", "Select files on the left first");
    if (sel.some((e) => !op.accepts.includes(e.file!.kind))) {
      if (op.accepts.includes("pdf")) return t("Yalnızca PDF dosyalarıyla çalışır", "Works with PDF files only");
      if (op.accepts.includes("image")) return t("Yalnızca görsellerle çalışır", "Works with images only");
      return t("Yalnızca Word / Excel / PowerPoint", "Word / Excel / PowerPoint only");
    }
    if (sel.length < op.min_inputs) return t(`En az ${op.min_inputs} dosya seçin`, `Select at least ${op.min_inputs} files`);
    if (sel.length > op.max_inputs)
      return op.max_inputs === 1 ? t("Tek dosya seçin", "Select a single file") : t(`En çok ${op.max_inputs} dosya`, `At most ${op.max_inputs} files`);
    return null;
  }

  function show(e: Event, title: string, body: string, why: string | null): void {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const above = r.bottom + 140 > window.innerHeight;
    tip = { title, body, why, x: Math.min(r.left, window.innerWidth - 300), y: above ? r.top - 8 : r.bottom + 8, above };
  }
</script>

<section class="tools" aria-label={t("Araçlar", "Tools")}>
  <div class="head">
    <input class="search" type="search" placeholder={t("Araç ara…", "Search tools…")} bind:value={query} />
    <span class="hint">{t("Açıklama için aracın üzerine gelin", "Hover a tool for its description")}</span>
  </div>

  {#if !query}
    <div class="featured">
      {#each FEATURED as c (c.mode)}
        <button
          class="feature"
          class:blocked={!single}
          aria-describedby="tool-tip"
          onclick={() => single && onopen(c.mode)}
          onmouseenter={(e) => show(e, t(c.tr, c.en), t(c.dtr, c.den), single ? null : t("Tek bir PDF seçin", "Select a single PDF"))}
          onfocus={(e) => show(e, t(c.tr, c.en), t(c.dtr, c.den), single ? null : t("Tek bir PDF seçin", "Select a single PDF"))}
          onmouseleave={() => (tip = null)}
          onblur={() => (tip = null)}
        >
          <span class="ficon" aria-hidden="true">{c.icon}</span>
          <strong>{t(c.tr, c.en)}</strong>
        </button>
      {/each}
    </div>
  {/if}

  <div class="columns">
    {#each groups as g (g.id)}
      <section class="group" aria-labelledby={`cat-${g.id}`}>
        <h3 id={`cat-${g.id}`}><span aria-hidden="true">{g.icon}</span> {t(g.label)}</h3>
        <ul>
          {#each g.ops as op (op.name)}
            {@const why = blocker(op)}
            <li>
              <button
                class="tool"
                class:blocked={why}
                aria-describedby="tool-tip"
                onclick={() => onpick(op)}
                onmouseenter={(e) => show(e, t(op.title), t(op.description), why)}
                onfocus={(e) => show(e, t(op.title), t(op.description), why)}
                onmouseleave={() => (tip = null)}
                onblur={() => (tip = null)}
              >
                <span class="dot" class:ready={!why} aria-hidden="true"></span>
                {t(op.title)}
              </button>
            </li>
          {/each}
        </ul>
      </section>
    {:else}
      <p class="empty">{t("Eşleşen araç yok.", "No matching tools.")}</p>
    {/each}
  </div>

  <div
    id="tool-tip"
    role="tooltip"
    class="tip"
    class:visible={tip}
    class:above={tip?.above}
    style:left={`${tip?.x ?? 0}px`}
    style:top={`${tip?.y ?? 0}px`}
  >
    {#if tip}
      <strong>{tip.title}</strong>
      <span>{tip.body}</span>
      {#if tip.why}<em>⚠ {tip.why}</em>{:else}<em class="ok">✓ {t("Seçili dosyalarla kullanılabilir", "Ready for the selected files")}</em>{/if}
    {/if}
  </div>
</section>

<style>
  .tools {
    display: grid;
    gap: 14px;
    align-content: start;
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 14px;
    align-items: center;
  }
  .search {
    max-width: 320px;
  }
  .hint {
    color: var(--muted);
    font-size: 0.8rem;
  }
  .featured {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 8px;
  }
  .feature {
    justify-content: flex-start;
    gap: 10px;
    padding: 10px 14px;
    border-radius: 12px;
    border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
    background: var(--surface);
    text-align: left;
  }
  .feature:hover:not(.blocked) {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .ficon {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 1rem;
  }
  .columns {
    columns: 210px;
    column-gap: 14px;
  }
  .group {
    break-inside: avoid;
    margin-bottom: 14px;
    padding: 10px 10px 8px;
    border-radius: 12px;
    background: var(--surface);
    border: 1px solid var(--border);
  }
  h3 {
    margin: 0 0 6px;
    padding: 0 4px;
    font-size: 0.75rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 1px;
  }
  .tool {
    width: 100%;
    min-height: 30px;
    justify-content: flex-start;
    gap: 8px;
    padding: 4px 6px;
    border: 0;
    border-radius: 7px;
    background: transparent;
    font-size: 0.88rem;
    text-align: left;
  }
  .tool:hover,
  .tool:focus-visible {
    background: var(--accent-soft);
    color: var(--accent);
  }
  .blocked {
    color: var(--muted);
  }
  .dot {
    flex: none;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--border-strong);
  }
  .dot.ready {
    background: var(--ok);
  }
  .tip {
    position: fixed;
    z-index: 50;
    display: grid;
    gap: 4px;
    width: 280px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--surface);
    border: 1px solid var(--border-strong);
    box-shadow: 0 10px 30px rgb(0 0 0 / 0.18);
    font-size: 0.85rem;
    pointer-events: none;
    opacity: 0;
    transform: translateY(4px);
    transition:
      opacity 0.12s,
      transform 0.12s;
  }
  .tip.above {
    transform: translateY(calc(-100% - 4px));
  }
  .tip.visible {
    opacity: 1;
    transform: translateY(0);
  }
  .tip.visible.above {
    transform: translateY(-100%);
  }
  .tip span {
    color: var(--muted);
  }
  .tip em {
    font-style: normal;
    font-size: 0.78rem;
    color: var(--warn);
  }
  .tip em.ok {
    color: var(--ok);
  }
  .empty {
    color: var(--muted);
  }
</style>
