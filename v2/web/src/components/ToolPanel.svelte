<script lang="ts">
  import { onDestroy, untrack } from "svelte";
  import { ApiError, cancelJob, fileUrl, type Job, type OpInfo, runOp, watchJob } from "../lib/api";
  import { formatBytes, t } from "../lib/i18n.svelte";
  import { workspace } from "../lib/workspace.svelte";
  import DataView from "./DataView.svelte";
  import SchemaForm from "./SchemaForm.svelte";

  let { op, onclose }: { op: OpInfo; onclose: () => void } = $props();

  function defaults(o: OpInfo): Record<string, unknown> {
    const v: Record<string, unknown> = {};
    for (const [k, f] of Object.entries(o.schema.properties ?? {})) {
      if (f.default !== undefined) v[k] = f.default;
      else if (f.type === "boolean") v[k] = false;
      else if (f.type === "array") v[k] = [];
      else if (f.type === "object" || f.$ref) v[k] = undefined;
      else v[k] = "";
    }
    return v;
  }

  // The panel is re-created per tool ({#key} in App), so the initial op is the op.
  let values = $state(defaults(untrack(() => op)));
  let fieldErrors = $state<Record<string, string>>({});
  let error = $state("");
  let job = $state<Job | null>(null);
  let busy = $state(false);
  let stop: (() => void) | null = null;

  const inputs = $derived(op.max_inputs === 0 ? [] : workspace.selected);
  const running = $derived(job !== null && (job.status === "queued" || job.status === "running"));

  const problem = $derived.by(() => {
    if (inputs.some((e) => !op.accepts.includes(e.file!.kind)))
      return t("Seçili dosyalar bu araçla uyumlu değil.", "The selected files don't fit this tool.");
    if (inputs.length < op.min_inputs)
      return t(`Bu araç için en az ${op.min_inputs} dosya seçin.`, `Select at least ${op.min_inputs} files for this tool.`);
    if (inputs.length > op.max_inputs)
      return op.max_inputs === 1
        ? t("Bu araç tek dosyayla çalışır — listeden birini seçin.", "This tool works on one file — pick one in the list.")
        : t(`En çok ${op.max_inputs} dosya seçin.`, `Select at most ${op.max_inputs} files.`);
    return "";
  });

  async function start(): Promise<void> {
    error = "";
    fieldErrors = {};
    busy = true;
    stop?.();
    try {
      job = await runOp(
        op.name,
        inputs.map((e) => ({ id: e.file!.id, password: e.password || undefined })),
        $state.snapshot(values),
      );
      stop = watchJob(job.id, (j) => (job = j));
    } catch (e) {
      if (e instanceof ApiError) {
        fieldErrors = e.fields;
        error = Object.keys(e.fields).length ? t("Lütfen işaretli alanları düzeltin.", "Please fix the marked fields.") : message(e);
      } else error = String(e);
    } finally {
      busy = false;
    }
  }

  function message(e: ApiError): string {
    if (e.status === 0) return t("Sunucuya ulaşılamıyor.", "Cannot reach the server.");
    if (e.status === 404) return t("Dosya bulunamadı — süresi dolmuş olabilir.", "File not found — it may have expired.");
    return e.message;
  }

  const dataUrl = $derived(
    job?.data ? URL.createObjectURL(new Blob([JSON.stringify(job.data, null, 2)], { type: "application/json" })) : undefined,
  );
  $effect(() => {
    const url = dataUrl;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  });

  onDestroy(() => stop?.());
</script>

<section class="panel" aria-labelledby="tool-title">
  <header>
    <button class="ghost" onclick={onclose} aria-label={t("Araçlara dön", "Back to tools")}>←</button>
    <div>
      <h2 id="tool-title">{t(op.title)}</h2>
      <p>{t(op.description)}</p>
    </div>
  </header>

  <div class="inputs">
    {#if op.max_inputs > 0}<span>{t("Girdi", "Input")}:</span>{/if}
    {#each inputs as e (e.key)}
      <span class="chip">{e.name}</span>
    {:else}
      {#if op.max_inputs > 0}<span class="muted">{t("Soldan dosya seçin", "Select files on the left")}</span>{/if}
    {/each}
  </div>

  <form
    onsubmit={(e) => {
      e.preventDefault();
      void start();
    }}
  >
    <SchemaForm schema={op.schema} bind:values errors={fieldErrors} />
    {#if problem}<p class="warn">{problem}</p>{/if}
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <div class="buttons">
      <button class="primary" type="submit" disabled={!!problem || busy || running}>
        {running ? t("Çalışıyor…", "Working…") : t("Başlat", "Start")}
      </button>
      {#if running && job}
        <button type="button" class="ghost" onclick={() => job && void cancelJob(job.id)}>{t("İptal", "Cancel")}</button>
      {/if}
    </div>
  </form>

  {#if job}
    <div class="job" aria-live="polite">
      {#if running}
        <progress max="1" value={job.status === "queued" ? undefined : job.progress}></progress>
        <span class="muted">{job.status === "queued" ? t("Sırada…", "Queued…") : `${Math.round(job.progress * 100)}%`}</span>
      {:else if job.status === "done"}
        {#if job.data}
          <div class="data">
            <DataView value={job.data} />
            <a
              class="button ghost small"
              download={`${op.name}.json`}
              href={dataUrl}
              >{t("JSON indir", "Download JSON")}</a
            >
          </div>
        {/if}
        {#if job.result}
        <div class="result">
          <div>
            <strong>{t("Hazır", "Ready")}</strong>
            <span class="muted">{job.result.name} · {formatBytes(job.result.size)}</span>
          </div>
          <a class="button primary" href={fileUrl(job.result.id)} download={job.result.name}>{t("İndir", "Download")}</a>
          {#if job.result.kind === "pdf"}
            <a class="button ghost" href={fileUrl(job.result.id, true)} target="_blank" rel="noopener">{t("Aç", "Open")}</a>
          {/if}
          <button
            class="ghost"
            onclick={() => {
              if (!job) return;
              const adopt = job.outputs.length === 1 ? job.outputs : job.outputs.filter((o) => o.kind === "pdf");
              for (const e of workspace.entries) e.selected = false;
              for (const o of adopt) workspace.adopt(o);
            }}>{t("Çalışma alanına ekle", "Add to workspace")}</button
          >
        </div>
        {/if}
      {:else if job.status === "failed"}
        <p class="error" role="alert">{job.error ? t(job.error) : t("İşlem başarısız.", "Operation failed.")}</p>
      {:else if job.status === "cancelled"}
        <p class="muted">{t("İptal edildi.", "Cancelled.")}</p>
      {/if}
    </div>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 16px;
    align-content: start;
    padding: 20px;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--border);
    max-width: 720px;
  }
  header {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }
  h2 {
    margin: 0;
    font-size: 1.25rem;
  }
  header p {
    margin: 4px 0 0;
    color: var(--muted);
  }
  .inputs {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    font-size: 0.85rem;
  }
  .chip {
    padding: 3px 9px;
    border-radius: 999px;
    background: var(--surface-2);
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  form {
    display: grid;
    gap: 14px;
  }
  .buttons {
    display: flex;
    gap: 8px;
  }
  .job {
    display: grid;
    gap: 8px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }
  progress {
    width: 100%;
  }
  .result {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
  }
  .result > div {
    display: grid;
    flex: 1 1 200px;
    min-width: 0;
  }
  .result .muted {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .data {
    display: grid;
    gap: 10px;
    justify-items: start;
  }
  .data > :global(*:first-child) {
    justify-self: stretch;
  }
  .muted {
    color: var(--muted);
  }
  .warn {
    margin: 0;
    color: var(--warn);
  }
  .error {
    margin: 0;
    color: var(--danger);
  }
</style>
