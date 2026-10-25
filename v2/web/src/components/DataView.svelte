<script lang="ts">
  import { t } from "../lib/i18n.svelte";
  import DataView from "./DataView.svelte";

  let { value, depth = 0 }: { value: unknown; depth?: number } = $props();

  const MAX_ROWS = 300;

  function isRecord(v: unknown): v is Record<string, unknown> {
    return typeof v === "object" && v !== null && !Array.isArray(v) && !isText(v);
  }

  /** Bilingual `{tr, en}` messages from the server render as one string. */
  function isText(v: unknown): v is { tr: string; en: string } {
    if (typeof v !== "object" || v === null || Array.isArray(v)) return false;
    const keys = Object.keys(v);
    return keys.length === 2 && "tr" in v && "en" in v;
  }

  function humanKey(k: string): string {
    return k.replaceAll("_", " ");
  }

  /** Columns of an array of flat-ish objects, or null if it isn't one. */
  function tableColumns(v: unknown[]): string[] | null {
    if (!v.length || !v.every(isRecord)) return null;
    const cols = new Set<string>();
    for (const row of v.slice(0, MAX_ROWS)) for (const k of Object.keys(row as object)) cols.add(k);
    return cols.size <= 12 ? [...cols] : null;
  }

  function scalar(v: unknown): string {
    if (v === null || v === undefined || v === "") return "—";
    if (typeof v === "boolean") return v ? "✓" : "✗";
    if (isText(v)) return t(v);
    if (Array.isArray(v) && v.every(isText)) return v.map((x) => t(x)).join(" · ");
    if (Array.isArray(v) && v.every((x) => typeof x !== "object")) return v.join(", ") || "—";
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
  }
</script>

{#if Array.isArray(value)}
  {@const cols = tableColumns(value)}
  {#if cols}
    <div class="scroll">
      <table>
        <thead><tr>{#each cols as c (c)}<th>{humanKey(c)}</th>{/each}</tr></thead>
        <tbody>
          {#each value.slice(0, MAX_ROWS) as row, i (i)}
            <tr>{#each cols as c (c)}<td>{scalar((row as Record<string, unknown>)[c])}</td>{/each}</tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if value.length > MAX_ROWS}<p class="more">+{value.length - MAX_ROWS}</p>{/if}
  {:else if value.every((x) => typeof x !== "object" || x === null)}
    <span>{scalar(value)}</span>
  {:else}
    <ol>{#each value.slice(0, MAX_ROWS) as item, i (i)}<li><DataView value={item} depth={depth + 1} /></li>{/each}</ol>
  {/if}
{:else if isRecord(value)}
  <dl class:nested={depth > 0}>
    {#each Object.entries(value) as [k, v] (k)}
      <dt>{humanKey(k)}</dt>
      <dd>
        {#if typeof v === "object" && v !== null && !isText(v) && !(Array.isArray(v) && (v.every((x) => typeof x !== "object") || v.every(isText)))}
          <DataView value={v} depth={depth + 1} />
        {:else}
          {scalar(v)}
        {/if}
      </dd>
    {/each}
  </dl>
{:else}
  <span>{scalar(value)}</span>
{/if}

<style>
  dl {
    display: grid;
    grid-template-columns: minmax(110px, max-content) 1fr;
    gap: 6px 14px;
    margin: 0;
  }
  dl.nested {
    padding-left: 10px;
    border-left: 2px solid var(--border);
  }
  dt {
    color: var(--muted);
    text-transform: capitalize;
  }
  dd {
    margin: 0;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .scroll {
    overflow: auto;
    max-height: 420px;
    border: 1px solid var(--border);
    border-radius: 10px;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.85rem;
  }
  th,
  td {
    padding: 6px 8px;
    border-bottom: 1px solid var(--border);
    text-align: left;
    vertical-align: top;
  }
  th {
    position: sticky;
    top: 0;
    background: var(--surface-2);
    text-transform: capitalize;
  }
  ol {
    margin: 0;
    padding-left: 18px;
    display: grid;
    gap: 8px;
  }
  .more {
    color: var(--muted);
    margin: 4px 0 0;
  }
</style>
