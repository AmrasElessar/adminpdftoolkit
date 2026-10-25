<script lang="ts">
  import { t } from "../i18n.svelte";
  import PageView from "./PageView.svelte";
  import type { PDFPageProxy } from "./pdf";

  export interface PlanItem {
    key: number;
    page: number; // 1-based source page, 0 = blank
    rotate: 0 | 90 | 180 | 270;
  }

  let {
    pages,
    busy = false,
    onsave,
  }: { pages: PDFPageProxy[]; busy?: boolean; onsave: (plan: { page: number; rotate: number }[]) => void } = $props();

  let seq = 0;
  const initial = (): PlanItem[] => pages.map((p) => ({ key: ++seq, page: p.pageNumber, rotate: 0 }));

  let plan = $state<PlanItem[]>(initial());
  let selected = $state<Set<number>>(new Set());
  let anchor = -1;
  let dragKey = $state<number | null>(null);
  let dropAt = $state<number | null>(null);
  let undoStack: PlanItem[][] = [];
  let redoStack: PlanItem[][] = [];
  let size = $state(150);

  const dirty = $derived(
    plan.length !== pages.length || plan.some((it, i) => it.page !== i + 1 || it.rotate !== 0),
  );

  function commit(next: PlanItem[]): void {
    undoStack.push($state.snapshot(plan) as PlanItem[]);
    if (undoStack.length > 200) undoStack.shift();
    redoStack = [];
    plan = next;
  }

  function undo(): void {
    const prev = undoStack.pop();
    if (!prev) return;
    redoStack.push($state.snapshot(plan) as PlanItem[]);
    plan = prev;
  }

  function redo(): void {
    const next = redoStack.pop();
    if (!next) return;
    undoStack.push($state.snapshot(plan) as PlanItem[]);
    plan = next;
  }

  function click(e: MouseEvent, i: number, key: number): void {
    const next = new Set(e.ctrlKey || e.metaKey ? selected : []);
    if (e.shiftKey && anchor >= 0) {
      const [a, b] = [Math.min(anchor, i), Math.max(anchor, i)];
      for (let j = a; j <= b; j++) next.add(plan[j]!.key);
    } else if ((e.ctrlKey || e.metaKey) && next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
      anchor = i;
    }
    selected = next;
  }

  const targets = $derived(selected.size ? plan.filter((p) => selected.has(p.key)) : []);

  function rotate(delta: 90 | -90): void {
    commit(plan.map((p) => (selected.has(p.key) ? { ...p, rotate: (((p.rotate + delta) % 360) + 360) % 360 as PlanItem["rotate"] } : p)));
  }

  function remove(): void {
    const next = plan.filter((p) => !selected.has(p.key));
    if (!next.length) return;
    commit(next);
    selected = new Set();
  }

  function duplicate(): void {
    const next: PlanItem[] = [];
    for (const p of plan) {
      next.push(p);
      if (selected.has(p.key)) next.push({ ...p, key: ++seq });
    }
    commit(next);
  }

  function insertBlank(): void {
    const last = Math.max(-1, ...plan.map((p, i) => (selected.has(p.key) ? i : -1)));
    const at = last >= 0 ? last + 1 : plan.length;
    commit([...plan.slice(0, at), { key: ++seq, page: 0, rotate: 0 }, ...plan.slice(at)]);
  }

  function reverse(): void {
    commit([...plan].reverse());
  }

  function moveSelectedTo(index: number): void {
    const moving = plan.filter((p) => selected.has(p.key) || p.key === dragKey);
    if (!moving.length) return;
    const keys = new Set(moving.map((m) => m.key));
    const before = plan.slice(0, index).filter((p) => !keys.has(p.key));
    const after = plan.slice(index).filter((p) => !keys.has(p.key));
    commit([...before, ...moving, ...after]);
  }

  function nudge(delta: -1 | 1): void {
    if (targets.length !== 1) return;
    const i = plan.findIndex((p) => p.key === targets[0]!.key);
    const j = i + delta;
    if (j < 0 || j >= plan.length) return;
    const next = [...plan];
    [next[i], next[j]] = [next[j]!, next[i]!];
    commit(next);
  }

  function keydown(e: KeyboardEvent): void {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
      e.preventDefault();
      if (e.shiftKey) redo();
      else undo();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
      e.preventDefault();
      redo();
    } else if ((e.key === "Delete" || e.key === "Backspace") && selected.size) {
      e.preventDefault();
      remove();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault();
      selected = new Set(plan.map((p) => p.key));
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<div class="organizer" tabindex="0" onkeydown={keydown} role="application" aria-label={t("Sayfa düzenleyici", "Page organiser")}>
  <div class="bar">
    <button onclick={() => rotate(-90)} disabled={!selected.size} title={t("Sola döndür", "Rotate left")}>⟲</button>
    <button onclick={() => rotate(90)} disabled={!selected.size} title={t("Sağa döndür", "Rotate right")}>⟳</button>
    <button onclick={duplicate} disabled={!selected.size}>{t("Çoğalt", "Duplicate")}</button>
    <button onclick={remove} disabled={!selected.size || selected.size >= plan.length}>{t("Sil", "Delete")}</button>
    <button onclick={insertBlank}>{t("Boş sayfa", "Blank page")}</button>
    <button onclick={reverse}>{t("Ters çevir", "Reverse")}</button>
    <button onclick={() => nudge(-1)} disabled={targets.length !== 1} aria-label={t("Öne al", "Move earlier")}>←</button>
    <button onclick={() => nudge(1)} disabled={targets.length !== 1} aria-label={t("Arkaya al", "Move later")}>→</button>
    <span class="sep"></span>
    <button onclick={undo} title="Ctrl+Z">↶</button>
    <button onclick={redo} title="Ctrl+Y">↷</button>
    <input type="range" min="90" max="260" bind:value={size} aria-label={t("Küçük resim boyutu", "Thumbnail size")} />
    <span class="sep"></span>
    <span class="count">{plan.length} {t("sayfa", "pages")}{selected.size ? ` · ${selected.size} ${t("seçili", "selected")}` : ""}</span>
    <button class="primary" disabled={!dirty || busy} onclick={() => onsave(plan.map(({ page, rotate }) => ({ page, rotate })))}>
      {busy ? t("Kaydediliyor…", "Saving…") : t("Değişiklikleri uygula", "Apply changes")}
    </button>
  </div>

  <ol class="grid" style:--size={`${size}px`}>
    {#each plan as item, i (item.key)}
      {@const src = item.page ? pages[item.page - 1] : undefined}
      <li
        class:selected={selected.has(item.key)}
        class:drop-before={dropAt === i}
        draggable="true"
        ondragstart={(e) => {
          dragKey = item.key;
          if (!selected.has(item.key)) selected = new Set([item.key]);
          e.dataTransfer?.setData("text/plain", String(item.key));
        }}
        ondragend={() => {
          dragKey = null;
          dropAt = null;
        }}
        ondragover={(e) => {
          e.preventDefault();
          const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
          dropAt = e.clientX > r.left + r.width / 2 ? i + 1 : i;
        }}
        ondrop={(e) => {
          e.preventDefault();
          if (dropAt !== null) moveSelectedTo(dropAt);
          dropAt = null;
        }}
      >
        <button class="thumb" onclick={(e) => click(e, i, item.key)} aria-pressed={selected.has(item.key)}>
          <div class="frame" style:transform={`rotate(${item.rotate}deg)`}>
            {#if src}
              <PageView page={src} scale={(size - 20) / Math.max(src.view[2]! - src.view[0]!, src.view[3]! - src.view[1]!)} textLayer={false} />
            {:else}
              <div class="blank" style:width={`${size * 0.7}px`} style:height={`${size * 0.99}px`}></div>
            {/if}
          </div>
          <span class="label">{i + 1}{#if item.page && item.page !== i + 1}<small> ← {item.page}</small>{/if}{#if !item.page}<small> {t("boş", "blank")}</small>{/if}</span>
        </button>
      </li>
    {/each}
  </ol>
</div>

<style>
  .organizer {
    display: grid;
    gap: 12px;
    outline: none;
  }
  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 2;
    padding: 8px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .bar button {
    min-height: 34px;
    padding: 4px 10px;
  }
  .sep {
    flex: 1;
  }
  .count {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(var(--size), 1fr));
    gap: 14px;
  }
  li {
    position: relative;
  }
  li.drop-before::before {
    content: "";
    position: absolute;
    left: -8px;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: 2px;
    background: var(--accent);
  }
  .thumb {
    display: grid;
    justify-items: center;
    gap: 6px;
    width: 100%;
    padding: 8px;
    border: 2px solid transparent;
    border-radius: 12px;
    background: transparent;
  }
  li.selected .thumb {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .frame {
    display: grid;
    place-items: center;
    height: var(--size);
    transition: transform 0.15s;
    pointer-events: none;
  }
  .frame :global(.page) {
    box-shadow: 0 1px 4px rgb(0 0 0 / 0.25);
  }
  .blank {
    background: #fff;
    box-shadow: 0 1px 4px rgb(0 0 0 / 0.25);
  }
  .label {
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }
  .label small {
    color: var(--muted);
  }
</style>
