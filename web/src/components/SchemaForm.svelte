<script lang="ts">
  import type { JsonSchema } from "../lib/api";
  import { t } from "../lib/i18n.svelte";
  import { workspace } from "../lib/workspace.svelte";

  let {
    schema,
    values = $bindable(),
    errors = {},
  }: { schema: JsonSchema; values: Record<string, unknown>; errors?: Record<string, string> } = $props();

  /** Pydantic emits `anyOf: [X, {type: null}]` for optionals: use X. */
  function unwrap(f: JsonSchema): JsonSchema {
    const inner = f.anyOf?.find((s) => s.type !== "null");
    return inner ? { ...inner, ...f, anyOf: undefined, type: inner.type, enum: inner.enum, items: inner.items } : f;
  }

  const fields = $derived(Object.entries(schema.properties ?? {}).map(([k, f]) => [k, unwrap(f)] as const));
  const jsonText = $state<Record<string, string>>({});

  function label(f: JsonSchema): string {
    return t(f.title_tr ?? f.title ?? "", f.title_en ?? f.title);
  }

  function help(f: JsonSchema): string {
    return f.help_tr ? t(f.help_tr, f.help_en) : "";
  }

  function visible(f: JsonSchema): boolean {
    const cond = f.ui?.show_if;
    return !cond || Object.entries(cond).every(([k, v]) =>
      Array.isArray(v) ? v.includes(values[k]) : values[k] === v,
    );
  }

  function optionLabel(f: JsonSchema, v: string | number): string {
    const o = f.ui?.options?.[String(v)];
    return o ? t(o) : String(v);
  }

  function kind(f: JsonSchema): string {
    if (f.ui?.widget === "file") return "file";
    if (f.type === "array" && f.items?.enum) return "multi";
    if (f.ui?.widget === "json" || f.type === "array" || f.type === "object" || f.$ref) return "json";
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

  function toggleMulti(name: string, v: string | number, on: boolean): void {
    const cur = Array.isArray(values[name]) ? (values[name] as (string | number)[]) : [];
    values[name] = on ? [...cur.filter((x) => x !== v), v] : cur.filter((x) => x !== v);
  }

  /** Raw text while the user types; otherwise the value pretty-printed.
   * (No state writes here: this runs during render.) */
  function jsonValue(name: string): string {
    if (name in jsonText) return jsonText[name] ?? "";
    const v = values[name];
    return v === undefined || v === null || v === "" ? "" : JSON.stringify(v, null, 2);
  }

  function setJson(name: string, raw: string): void {
    jsonText[name] = raw;
    try {
      values[name] = raw.trim() ? JSON.parse(raw) : null;
    } catch {
      values[name] = raw; // the server reports it as invalid
    }
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
          <label for={id} id={`${id}-label`}>{label(f)}</label>
          {#if k === "file"}
            {@const options = workspace.entries.filter((e) => e.file && (!f.ui?.accept?.length || f.ui.accept.includes(e.file.kind)))}
            <select {id} value={String(values[name] ?? "")} onchange={(e) => (values[name] = e.currentTarget.value)}>
              <option value="">{options.length ? t("— Dosya seçin —", "— Choose a file —") : t("Önce soldan uygun dosya yükleyin", "Upload a suitable file on the left first")}</option>
              {#each options as e (e.key)}
                <option value={e.file!.id}>{e.name}</option>
              {/each}
            </select>
          {:else if k === "multi"}
            <div class="multi" role="group" aria-labelledby={`${id}-label`}>
              {#each f.items?.enum ?? [] as v (v)}
                <label class="pill">
                  <input
                    type="checkbox"
                    checked={Array.isArray(values[name]) && (values[name] as unknown[]).includes(v)}
                    onchange={(e) => toggleMulti(name, v, e.currentTarget.checked)}
                  />
                  {optionLabel(f, v)}
                </label>
              {/each}
            </div>
          {:else if k === "json" || k === "textarea"}
            <textarea
              {id}
              rows="6"
              spellcheck="false"
              class:mono={k === "json"}
              value={k === "json" ? jsonValue(name) : String(values[name] ?? "")}
              oninput={(e) => (k === "json" ? setJson(name, e.currentTarget.value) : (values[name] = e.currentTarget.value))}
            ></textarea>
          {:else if k === "enum"}
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
  .multi {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .pill {
    display: inline-flex;
    gap: 6px;
    align-items: center;
    padding: 4px 10px;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    cursor: pointer;
  }
  textarea {
    width: 100%;
    padding: 8px 10px;
    border-radius: 10px;
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: inherit;
    font: inherit;
    resize: vertical;
  }
  textarea.mono {
    font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    font-size: 0.85rem;
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
