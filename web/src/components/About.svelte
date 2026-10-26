<script lang="ts">
  import { getAbout, type About } from "../lib/api";
  import { i18n } from "../lib/i18n.svelte";

  let { open = $bindable(false) }: { open: boolean } = $props();

  type Lang = "tr" | "en";
  let dialog: HTMLDialogElement;
  let data = $state<About | null>(null);
  let failed = $state(false);
  // The page is one language at a time — Turkish and English never mixed.
  let lang = $state<Lang>(i18n.lang);

  $effect(() => {
    if (open && !dialog.open) {
      lang = i18n.lang;
      dialog.showModal();
      if (!data) {
        getAbout()
          .then((d) => (data = d))
          .catch(() => (failed = true));
      }
    } else if (!open && dialog.open) dialog.close();
  });

  const LABELS = {
    tr: {
      title: "Hakkında ve Lisanslar",
      licence: "Lisans",
      source: "Kaynak kod",
      systems: "Çalıştığı sistemler",
      python: "Python kütüphaneleri",
      pythonIntro: "Bu kurulumda gerçekten yüklü olan paketlerin tamamı, kendi kayıtlarından okunur.",
      direct: "Doğrudan kullanılanlar",
      transitive: "Bunların kurduğu paketler",
      via: "ile gelir",
      web: "Web arayüzü (tarayıcıya gönderilen kod)",
      webIntro: "Her derlemede otomatik toplanır; tam lisans metinleri aşağıdaki bağlantıda.",
      bundled: "Bu pakete gömülü dosyalar",
      bundledIntro: "Paketle gelen araçlar ve tüm dosyaları; her dosya kullanımdan önce SHA-256 ile doğrulanır.",
      files: "dosya",
      methods: "Yöntemler ve algoritmalar",
      notes: "Notlar",
      runtime: "Bu kurulum",
      fullTexts: "Tüm lisans metinleri (licenses.txt)",
      name: "Ad",
      version: "Sürüm",
      role: "Görev",
      where: "Nerede",
      sourceCol: "Kaynak",
      loading: "Yükleniyor…",
      error: "Bilgi alınamadı.",
      close: "Kapat",
    },
    en: {
      title: "About & Licences",
      licence: "Licence",
      source: "Source code",
      systems: "Supported systems",
      python: "Python libraries",
      pythonIntro: "Every package actually installed in this copy, read from the packages' own metadata.",
      direct: "Used directly",
      transitive: "Pulled in by those",
      via: "via",
      web: "Web UI (code sent to the browser)",
      webIntro: "Collected automatically on every build; full licence texts at the link below.",
      bundled: "Files bundled in this package",
      bundledIntro: "Tools shipped with the package and all their files; each is checked by SHA-256 before use.",
      files: "files",
      methods: "Methods and algorithms",
      notes: "Notes",
      runtime: "This installation",
      fullTexts: "All licence texts (licenses.txt)",
      name: "Name",
      version: "Version",
      role: "Role",
      where: "Where",
      sourceCol: "Source",
      loading: "Loading…",
      error: "Could not load the details.",
      close: "Close",
    },
  } as const;

  const L = $derived(LABELS[lang]);
  const direct = $derived(data?.python_packages.filter((p) => !p.via) ?? []);
  const transitive = $derived(data?.python_packages.filter((p) => p.via) ?? []);
  const role = (name: string) => data?.python_roles[name.toLowerCase().replaceAll("_", "-")]?.[lang] ?? "";
</script>

<dialog bind:this={dialog} onclose={() => (open = false)} aria-labelledby="about-title" lang={lang}>
  <header>
    <h2 id="about-title">{L.title}</h2>
    <div class="tabs" role="tablist" aria-label="Dil / Language">
      <button role="tab" aria-selected={lang === "tr"} class:on={lang === "tr"} onclick={() => (lang = "tr")}>Türkçe</button>
      <button role="tab" aria-selected={lang === "en"} class:on={lang === "en"} onclick={() => (lang = "en")}>English</button>
    </div>
    <button class="icon" onclick={() => dialog.close()} aria-label={L.close}>✕</button>
  </header>

  {#if failed}
    <p class="error">{L.error}</p>
  {:else if !data}
    <p class="muted">{L.loading}</p>
  {:else}
    <div class="body" role="tabpanel">
      <p class="lead">
        <strong>Admin PDF Toolkit {data.version}</strong> · {L.licence}: <a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" rel="noopener noreferrer">{data.license}</a>
        · <a href={data.source} target="_blank" rel="noopener noreferrer">{L.source}</a>
      </p>
      <p>{data.intro[lang]}</p>

      <h3>{L.systems}</h3>
      <h4>{data.systems.server_title[lang]}</h4>
      <ul>{#each data.systems.server as s (s.name.en)}<li><strong>{s.name[lang]}</strong> — {s.how[lang]}</li>{/each}</ul>
      <h4>{data.systems.client_title[lang]}</h4>
      <ul>{#each data.systems.clients as s (s.name.en)}<li><strong>{s.name[lang]}</strong> — {s.how[lang]}</li>{/each}</ul>

      <h3>{data.first_run_title[lang]}</h3>
      <p>{data.first_run_intro[lang]}</p>
      <ul>
        {#each data.first_run as w (w.title.en)}
          <li><strong>{w.system} — {w.title[lang]}:</strong> {w.steps[lang]}</li>
        {/each}
      </ul>
      <p class="muted small">{data.verify[lang]}</p>

      <h3>{L.python} ({data.python_packages.length})</h3>
      <p class="muted small">{L.pythonIntro}</p>
      <h4>{L.direct} ({direct.length})</h4>
      <div class="scroll">
        <table>
          <thead><tr><th>{L.name}</th><th>{L.version}</th><th>{L.licence}</th><th>{L.role}</th></tr></thead>
          <tbody>
            {#each direct as p (p.name)}
              <tr><td><a href={p.url} target="_blank" rel="noopener noreferrer">{p.name}</a></td><td>{p.version}</td><td>{p.license}</td><td>{role(p.name)}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <h4>{L.transitive} ({transitive.length})</h4>
      <div class="scroll">
        <table>
          <thead><tr><th>{L.name}</th><th>{L.version}</th><th>{L.licence}</th><th>{L.where}</th></tr></thead>
          <tbody>
            {#each transitive as p (p.name)}
              <tr><td><a href={p.url} target="_blank" rel="noopener noreferrer">{p.name}</a></td><td>{p.version}</td><td>{p.license}</td><td>{lang === "tr" ? `${p.via} ${L.via}` : `${L.via} ${p.via}`}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>

      <h3>{L.web}</h3>
      <p class="muted small">{L.webIntro}</p>
      <div class="scroll">
        <table>
          <thead><tr><th>{L.name}</th><th>{L.version}</th><th>{L.licence}</th></tr></thead>
          <tbody>
            {#each data.web_packages as p (p.name)}
              <tr><td><a href={p.url} target="_blank" rel="noopener noreferrer">{p.name}</a></td><td>{p.version}</td><td>{p.license}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>

      {#if data.bundled.length}
        <h3>{L.bundled}</h3>
        <p class="muted small">{L.bundledIntro}</p>
        {#each data.bundled as b (b.name)}
          <details>
            <summary><strong>{b.name}</strong> {b.version} — {b.files.length} {L.files}</summary>
            <ul class="files">
              {#each Object.entries(b.sources) as [key, src] (key)}<li><a href={src.url} target="_blank" rel="noopener noreferrer">{key}</a> <code>{src.sha256.slice(0, 16)}…</code></li>{/each}
            </ul>
            <p class="filelist">{b.files.join(" · ")}</p>
          </details>
        {/each}
      {/if}

      {#each data.groups as g (g.id)}
        <h3>{g.title[lang]}</h3>
        {#if g.intro[lang]}<p class="muted small">{g.intro[lang]}</p>{/if}
        <div class="scroll">
          <table>
            <thead><tr><th>{L.name}</th><th>{L.licence}</th><th>{L.role}</th><th>{L.where}</th></tr></thead>
            <tbody>
              {#each g.items as item (item.name)}
                <tr><td><a href={item.url} target="_blank" rel="noopener noreferrer">{item.name}</a></td><td>{item.license}</td><td>{item.role[lang]}</td><td>{item.where[lang]}</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/each}

      <h3>{data.methods_title[lang]}</h3>
      <p class="muted small">{data.methods_intro[lang]}</p>
      <div class="scroll">
        <table>
          <thead><tr><th>{L.name}</th><th>{L.where}</th><th>{L.sourceCol}</th></tr></thead>
          <tbody>
            {#each data.methods as m (m.name.en)}<tr><td>{m.name[lang]}</td><td>{m.where[lang]}</td><td>{m.source}</td></tr>{/each}
          </tbody>
        </table>
      </div>

      <h3>{L.notes}</h3>
      <ul>{#each data.notes as n (n.en)}<li>{n[lang]}</li>{/each}</ul>

      <h3>{L.runtime}</h3>
      <p class="muted small">Python {data.runtime.python} ({data.runtime.implementation}) · {data.runtime.system}</p>
      <p><a class="button small" href="/licenses.txt" target="_blank" rel="noopener">{L.fullTexts}</a></p>
    </div>
  {/if}
</dialog>

<style>
  dialog {
    width: min(980px, calc(100vw - 24px));
    max-height: calc(100dvh - 32px);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text);
    padding: 0;
  }
  dialog::backdrop {
    background: rgb(0 0 0 / 0.4);
  }
  header {
    position: sticky;
    top: 0;
    z-index: 1;
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    align-items: center;
    padding: 14px 18px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  h2 {
    margin: 0;
    font-size: 1.15rem;
    flex: 1;
  }
  .tabs {
    display: flex;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  .tabs button {
    border: 0;
    border-radius: 0;
    min-height: 32px;
    padding: 4px 12px;
    background: transparent;
  }
  .tabs button.on {
    background: var(--accent);
    color: var(--on-accent);
  }
  .body {
    padding: 6px 18px 18px;
    font-size: 0.9rem;
  }
  .lead {
    margin-top: 10px;
  }
  h3 {
    margin: 20px 0 6px;
    font-size: 1rem;
  }
  h4 {
    margin: 12px 0 4px;
    font-size: 0.88rem;
    color: var(--muted);
  }
  ul {
    margin: 4px 0;
    padding-left: 20px;
    display: grid;
    gap: 4px;
  }
  .scroll {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }
  th,
  td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--border);
    text-align: left;
    vertical-align: top;
  }
  th {
    color: var(--muted);
    font-weight: 600;
  }
  td:first-child {
    white-space: nowrap;
  }
  .files {
    font-size: 0.8rem;
  }
  .filelist {
    font: 0.75rem/1.5 ui-monospace, monospace;
    color: var(--muted);
    word-break: break-all;
  }
  .small {
    font-size: 0.8rem;
  }
  .muted {
    color: var(--muted);
  }
  .error {
    color: var(--danger);
    padding: 18px;
  }
</style>
