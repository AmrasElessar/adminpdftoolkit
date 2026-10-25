<script lang="ts">
  import type { JsonSchema } from "../lib/api";
  import { t } from "../lib/i18n.svelte";

  let {
    schema,
    values = $bindable(),
    errors = {},
  }: { schema: JsonSchema; values: Record<string, unknown>; errors?: Record<string, string> } = $props();

  const fields = $derived(Object.entries(schema.properties ?? {}));

  function label(f: JsonSchema): string {
    return t(f.title_tr ?? f.title ?? "", f.title_en ?? f.title);
  }

  function help(f: JsonSchema): string {
    return f.help_tr ? t(f.help_tr, f.help_en) : "";
  }

  function visible(f: JsonSchema): boolean {
    const cond = f.ui?.show_if;
    return !cond || Object.entries(cond).every(([k, v]) => values[k] === v);
  }

  function optionLabel(f: JsonSchema, v: string | number): string {
    const o = f.ui?.options?.[String(v)];
    return o ? t(o) : String(v);
  }

  function kind(f: JsonSchema): string {
    if (f.enum) return "enum";
    if (f.type === "boolean") return "bool";
    if (f.type === "integer" || f.type === "number") return f.ui?.widget === "range" ? "range" : "number";
    return f.ui?.widget ?? "text";
  }

  function setNumber(name: string, raw: string, integer: boolean): void {
    // Keep the raw string while the field is mid-edit or empty so the
    // server's validation, not a silent NaN, reports the problem.
    const n = integer ? Number.parseInt(raw, 10) : Number.parseFloat(raw);
    values[name] = raw.trim() === "" || Number.isNaN(n) ? raw : n;
  }

  function setEnum(name: string, f: JsonSchema, raw: string): void {
    const match = f.enum?.find((v) => String(v) === raw);
    values[name] = match ?? raw;
  }
</script>

<div class="form">
  {#each fields as [name, f] (name)}
    {#if visible(f)}
      {@const id = `f-${name}`}
      {@const k = kind(f)}
      <div class="field" class:check={k === "bool"} class:invalid={errors[name]}>
        {#if k === "bool"}
          <label for={id}>
            <input {id} type="checkbox" bind:checked={() => Boolean(values[name]), (v) => (values[name] = v)} />
            <span>{label(f)}</span>
          </label>
        {:else}
          <label for={id}>{label(f)}</label>
          {#if k === "enum"}
            <select {id} value={String(values[name])} onchange={(e) => setEnum(name, f, e.currentTarget.value)}>
              {#each f.enum ?? [] as v (v)}
                <option value={String(v)}>{optionLabel(f, v)}</option>
              {/each}
            </select>
          {:else if k === "number" || k === "range"}
            <div class="row">
              <input
                {id}
                type={k}
                min={f.minimum}
                max={f.maximum}
                step={f.ui?.step ?? (f.type === "integer" ? 1 : "any")}
                value={values[name]}
                oninput={(e) => setNumber(name, e.currentTarget.value, f.type === "integer")}
              />
              {#if k === "range"}<output for={id}>{values[name]}</output>{/if}
            </div>
          {:else if k === "color"}
            <div class="row">
              <input
                type="color"
                aria-label={label(f)}
                value={`#${String(values[name] ?? "#000000").replace("#", "")}`}
                oninput={(e) => (values[name] = e.currentTarget.value)}
              />
              <input {id} type="text" maxlength="7" bind:value={() => String(values[name] ?? ""), (v) => (values[name] = v)} />
            </div>
          {:else}
            <input
              {id}
              type={k === "password" ? "password" : "text"}
              autocomplete={k === "password" ? "new-password" : "off"}
              maxlength={f.maxLength}
              required={(schema.required ?? []).includes(name) && (f.minLength ?? 0) > 0}
              bind:value={() => String(values[name] ?? ""), (v) => (values[name] = v)}
            />
          {/if}
        {/if}
        {#if errors[name]}
          <p class="error" role="alert">{errors[name]}</p>
        {:else if help(f)}
          <p class="help">{help(f)}</p>
        {/if}
      </div>
    {/if}
  {/each}
</div>

<style>
  .form {
    display: grid;
    gap: 14px;
  }
  .field {
    display: grid;
    gap: 6px;
  }
  .field > label {
    font-weight: 550;
    font-size: 0.9rem;
  }
  .check label {
    display: flex;
    gap: 8px;
    align-items: center;
    font-weight: 450;
    cursor: pointer;
  }
  .row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .row input[type="range"] {
    flex: 1;
  }
  .row input[type="text"] {
    width: 7.5em;
  }
  output {
    min-width: 3ch;
    font-variant-numeric: tabular-nums;
  }
  .help,
  .error {
    margin: 0;
    font-size: 0.8rem;
    color: var(--muted);
  }
  .error {
    color: var(--danger);
  }
  .invalid input,
  .invalid select {
    border-color: var(--danger);
  }
</style>
