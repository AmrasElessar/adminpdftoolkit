<script lang="ts">
  import { t } from "../i18n.svelte";
  import { ACTIONS, type Action, type KvkkState } from "./state.svelte";

  let {
    kvkk,
    busy = false,
    ongo,
    onapply,
    scanned = false,
    onocr,
  }: {
    kvkk: KvkkState;
    busy?: boolean;
    ongo: (page: number) => void;
    onapply: () => void;
    scanned?: boolean;
    onocr?: () => void;
  } = $props();

  let open = $state<Record<string, boolean>>({});

  function kindLabel(kind: string): string {
    const k = kvkk.kinds[kind];
    return k ? t(k) : kind === "manual" ? t("Elle seçilen alan", "Manual area") : kind;
  }

  function groupAction(items: { action: Action }[]): Action | "" {
    const first = items[0]?.action;
    return items.every((i) => i.action === first) ? (first ?? "") : "";
  }
</script>

<div class="kvkk">
  {#if kvkk.status === "scanning"}
    <div class="state">
      <p>{t("Belge kişisel veri için taranıyor…", "Scanning the document for personal data…")}</p>
      <progress max="1" value={kvkk.progress}></progress>
    </div>
  {:else if kvkk.status === "error"}
    <div class="state">
      <p class="error">{t("Tarama başarısız oldu.", "The scan failed.")}</p>
      <button class="small" onclick={() => kvkk.scan()}>{t("Tekrar dene", "Retry")}</button>
    </div>
  {:else if kvkk.status === "ready"}
    <div class="summary">
      <strong>{kvkk.findings.length}</strong>
      {t("bulgu", "findings")} · {kvkk.active.length} {t("işlenecek", "to treat")}
      <label class="all">
        {t("Tümüne", "All")}:
        <select onchange={(e) => kvkk.setAll(e.currentTarget.value as Action)} aria-label={t("Tümüne uygula", "Apply to all")}>
          <option value="" selected disabled>—</option>
          {#each ACTIONS as a (a.id)}<option value={a.id}>{t(a.tr, a.en)}</option>{/each}
        </select>
      </label>
    </div>
    {#if scanned}
      <div class="ocr">
        <p>{t("Belge taranmış görünüyor; metin görsel olduğu için kişisel veriler bulunamaz. Önce OCR uygulayın.", "The document looks scanned, so its text can't be searched. Run OCR first.")}</p>
        {#if onocr}<button class="primary small" disabled={busy} onclick={onocr}>{t("OCR uygula ve yeniden tara", "Run OCR and rescan")}</button>{/if}
      </div>
    {/if}
    {#if !kvkk.findings.length}
      <p class="muted">{t("Kişisel veri bulunamadı. Sayfada sürükleyerek elle alan ekleyebilirsiniz.", "No personal data found. Drag on a page to add an area by hand.")}</p>
    {/if}
    <div class="groups">
      {#each kvkk.groups() as g (g.kind)}
        {@const special = kvkk.kinds[g.kind]?.special}
        <section class="group" class:special>
          <header>
            <button class="toggle" onclick={() => (open[g.kind] = !open[g.kind])} aria-expanded={!!open[g.kind]}>
              {open[g.kind] ? "▾" : "▸"} {kindLabel(g.kind)} <span class="count">{g.items.length}</span>
            </button>
            <select
              value={groupAction(g.items)}
              aria-label={`${kindLabel(g.kind)} — ${t("işlem", "action")}`}
              onchange={(e) => kvkk.setKind(g.kind, e.currentTarget.value as Action)}
            >
              {#if !groupAction(g.items)}<option value="" disabled>{t("Karışık", "Mixed")}</option>{/if}
              {#each ACTIONS as a (a.id)}<option value={a.id}>{t(a.tr, a.en)}</option>{/each}
            </select>
          </header>
          {#if special}
            <p class="hint">{t("KVKK md. 6 özel nitelikli veri olabilir — bağlamı kontrol edin.", "May be special-category data (KVKK art. 6) — check the context.")}</p>
          {/if}
          {#if open[g.kind]}
            <ul>
              {#each g.items as f (f.id)}
                <li class:focused={kvkk.focused === f.id}>
                  <button
                    class="item"
                    onclick={() => {
                      kvkk.focused = f.id;
                      ongo(f.page);
                    }}
                  >
                    <span class="page">s.{f.page}</span>
                    <span class="text">{f.text || t("(alan)", "(area)")}</span>
                  </button>
                  <select bind:value={f.action} aria-label={t("İşlem", "Action")}>
                    {#each ACTIONS as a (a.id)}<option value={a.id}>{t(a.tr, a.en)}</option>{/each}
                  </select>
                  {#if f.kind === "manual"}
                    <button class="icon" onclick={() => kvkk.remove(f.id)} aria-label={t("Kaldır", "Remove")}>✕</button>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </section>
      {/each}
    </div>
    <p class="note">
      {t(
        "Tüm işlemler alttaki metni kalıcı olarak siler. En güvenlisi karartmadır; bulanıklaştırma görünümü korur.",
        "Every treatment permanently removes the text underneath. Black-out is safest; blur keeps the look.",
      )}
    </p>
    <label class="secure">
      <input type="checkbox" bind:checked={kvkk.flatten} />
      <span>
        <strong>{t("Ekstra güvenli PDF", "Extra-secure PDF")}</strong>
        {t(
          "Sayfalar görsele çevrilip yeniden PDF yapılır: içinde metin ya da gizli nesne kalmaz, hiçbir araçla geri getirilemez. Metin artık seçilemez.",
          "Pages are turned into images and rebuilt as a PDF: no text or hidden objects remain, nothing can be recovered. Text can no longer be selected.",
        )}
      </span>
    </label>
    <button class="primary apply" disabled={busy || !kvkk.active.length} onclick={onapply} title="Ctrl+S">
      {busy ? t("Uygulanıyor…", "Applying…") : `${t("Uygula", "Apply")} (${kvkk.active.length})`}
    </button>
  {/if}
</div>

<style>
  .secure {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface-2);
    color: var(--muted);
    font-size: 0.8rem;
    cursor: pointer;
  }
  .secure strong {
    display: block;
    color: var(--text);
    font-size: 0.85rem;
  }
  .secure input {
    margin-top: 2px;
    width: 18px;
    height: 18px;
  }
  .kvkk {
    display: grid;
    gap: 10px;
    align-content: start;
    font-size: 0.85rem;
  }
  .state {
    display: grid;
    gap: 8px;
  }
  .summary {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }
  .all {
    margin-left: auto;
    display: flex;
    gap: 4px;
    align-items: center;
    color: var(--muted);
  }
  select {
    width: auto;
    padding: 3px 6px;
    font-size: 0.8rem;
  }
  .groups {
    display: grid;
    gap: 6px;
  }
  .group {
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 6px;
  }
  .group.special {
    border-color: color-mix(in srgb, var(--warn) 50%, var(--border));
  }
  header {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .toggle {
    flex: 1;
    justify-content: flex-start;
    min-height: 28px;
    padding: 2px 4px;
    border: 0;
    background: transparent;
    font-weight: 600;
    text-align: left;
  }
  .count {
    margin-left: 4px;
    padding: 0 6px;
    border-radius: 999px;
    background: var(--surface-2);
    font-weight: 500;
    font-size: 0.75rem;
  }
  .hint {
    margin: 4px 4px 0;
    color: var(--warn);
    font-size: 0.75rem;
  }
  ul {
    list-style: none;
    margin: 6px 0 0;
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
  li.focused {
    background: var(--accent-soft);
  }
  .item {
    flex: 1;
    min-width: 0;
    justify-content: flex-start;
    gap: 6px;
    min-height: 26px;
    padding: 2px 4px;
    border: 0;
    background: transparent;
    font-size: 0.8rem;
  }
  .page {
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: ui-monospace, monospace;
  }
  .ocr {
    display: grid;
    gap: 6px;
    padding: 8px;
    border-radius: 8px;
    background: var(--accent-soft);
  }
  .ocr p {
    margin: 0;
  }
  .note,
  .muted {
    margin: 0;
    color: var(--muted);
    font-size: 0.75rem;
  }
  .error {
    color: var(--danger);
  }
  .apply {
    width: 100%;
  }
</style>
