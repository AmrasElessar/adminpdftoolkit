<script lang="ts">
  import { ApiError, listOps, loadSession, type OpInfo, pair, type Session } from "./lib/api";
  import { i18n, setLang, t } from "./lib/i18n.svelte";
  import FileTray from "./components/FileTray.svelte";
  import ToolGrid from "./components/ToolGrid.svelte";
  import ToolPanel from "./components/ToolPanel.svelte";
  import { type Entry, workspace } from "./lib/workspace.svelte";

  type ViewMode = "view" | "organize" | "edit";
  let viewing = $state<{ entry: Entry; mode: ViewMode } | null>(null);
  // pdf.js is ~1 MB: load the viewer only when a PDF is opened.
  const loadViewer = () => import("./lib/viewer/Viewer.svelte").then((m) => m.default);

  function openViewer(entry: Entry, mode: ViewMode = "view"): void {
    active = null;
    viewing = { entry, mode };
  }

  let session = $state<Session | null>(null);
  let ops = $state<OpInfo[]>([]);
  let active = $state<OpInfo | null>(null);
  let fatal = $state("");
  let pairKey = $state("");
  let pairError = $state("");

  async function boot(): Promise<void> {
    fatal = "";
    try {
      session = await loadSession();
      if (session.paired) ops = await listOps();
    } catch (e) {
      fatal = e instanceof ApiError && e.status === 403 ? t("Bu cihazdan erişim kapalı.", "Access from this device is disabled.") : t("Sunucuya bağlanılamadı.", "Could not connect to the server.");
    }
  }

  async function submitPair(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    pairError = "";
    try {
      await pair(pairKey.trim());
      pairKey = "";
      await boot();
    } catch (err) {
      pairError =
        err instanceof ApiError && err.status === 429
          ? t("Çok fazla deneme — bir dakika bekleyin.", "Too many attempts — wait a minute.")
          : t("Anahtar hatalı.", "Wrong key.");
    }
  }

  // Pairing links carry the key in the fragment (never sent to the server
  // in logs or Referer): http://host:8000/#pair=KEY
  const fragmentKey = new URLSearchParams(location.hash.slice(1)).get("pair");
  if (fragmentKey) {
    pairKey = fragmentKey;
    history.replaceState(null, "", location.pathname);
  }

  void boot().then(() => {
    if (fragmentKey && session && !session.paired) {
      void submitPair(new SubmitEvent("submit"));
    }
  });

  $effect(() => {
    document.documentElement.lang = i18n.lang;
    document.title = active ? `${t(active.title)} · Admin PDF Toolkit` : "Admin PDF Toolkit";
  });
</script>

<div class="app">
  <header class="top">
    <div class="brand">
      <img src="/icon.svg" alt="" width="28" height="28" />
      <span>Admin PDF Toolkit</span>
      {#if session}<small>v{session.version}</small>{/if}
    </div>
    <div class="lang" role="group" aria-label={t("Dil", "Language")}>
      <button class:on={i18n.lang === "tr"} aria-pressed={i18n.lang === "tr"} onclick={() => setLang("tr")}>TR</button>
      <button class:on={i18n.lang === "en"} aria-pressed={i18n.lang === "en"} onclick={() => setLang("en")}>EN</button>
    </div>
  </header>

  {#if fatal}
    <main class="center">
      <p class="error">{fatal}</p>
      <button class="primary" onclick={boot}>{t("Tekrar dene", "Retry")}</button>
    </main>
  {:else if !session}
    <main class="center"><p class="muted">{t("Yükleniyor…", "Loading…")}</p></main>
  {:else if !session.paired}
    <main class="center">
      <form class="pair" onsubmit={submitPair}>
        <h1>{t("Cihazı eşleştir", "Pair this device")}</h1>
        <p class="muted">
          {t(
            "Sunucu bilgisayarında gösterilen eşleştirme anahtarını girin.",
            "Enter the pairing key shown on the server computer.",
          )}
        </p>
        <input type="password" autocomplete="off" aria-label={t("Eşleştirme anahtarı", "Pairing key")} bind:value={pairKey} required />
        {#if pairError}<p class="error" role="alert">{pairError}</p>{/if}
        <button class="primary" type="submit">{t("Eşleştir", "Pair")}</button>
      </form>
    </main>
  {:else}
    <main class="work" class:viewing={!!viewing}>
      <FileTray maxUploadMb={session.max_upload_mb} onopen={(e) => openViewer(e)} />
      <div class="stage">
        {#if viewing}
          {#key viewing.entry.key}
            {#await loadViewer()}
              <p class="muted">{t("Görüntüleyici yükleniyor…", "Loading viewer…")}</p>
            {:then Viewer}
              <Viewer
                entry={viewing.entry}
                initialMode={viewing.mode}
                onclose={() => (viewing = null)}
                onresult={(file, mode, password) => {
                  for (const e of workspace.entries) e.selected = false;
                  openViewer(workspace.adopt(file, true, password), mode);
                }}
              />
            {/await}
          {/key}
        {:else if active}
          {#key active.name}
            <ToolPanel op={active} onclose={() => (active = null)} />
          {/key}
        {:else}
          <ToolGrid {ops} onpick={(op) => (active = op)} onopen={(mode) => workspace.selected[0] && openViewer(workspace.selected[0], mode)} />
        {/if}
      </div>
    </main>
  {/if}
</div>

<style>
  .app {
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
  }
  .top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    position: sticky;
    top: 0;
    z-index: 5;
  }
  .brand {
    display: flex;
    gap: 10px;
    align-items: center;
    font-weight: 650;
  }
  .brand small {
    font-weight: 450;
    color: var(--muted);
  }
  .lang {
    display: flex;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  .lang button {
    border: 0;
    border-radius: 0;
    padding: 5px 10px;
    background: transparent;
    color: var(--muted);
  }
  .lang button.on {
    background: var(--accent);
    color: var(--on-accent);
  }
  .work {
    flex: 1;
    display: grid;
    grid-template-columns: minmax(280px, 360px) 1fr;
    gap: 20px;
    padding: 20px;
    align-items: start;
  }
  .stage {
    min-width: 0;
  }
  .work.viewing {
    grid-template-columns: 1fr;
  }
  .work.viewing :global(.tray) {
    display: none;
  }
  .work :global(.tray) {
    position: sticky;
    top: 72px;
    max-height: calc(100dvh - 92px);
  }
  .center {
    flex: 1;
    display: grid;
    place-content: center;
    justify-items: center;
    gap: 12px;
    padding: 16px;
  }
  .pair {
    display: grid;
    gap: 12px;
    width: min(380px, 100%);
    padding: 24px;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--border);
  }
  .pair h1 {
    margin: 0;
    font-size: 1.3rem;
  }
  .pair p {
    margin: 0;
  }
  .muted {
    color: var(--muted);
  }
  .error {
    color: var(--danger);
    margin: 0;
  }
  @media (max-width: 760px) {
    .work {
      grid-template-columns: 1fr;
      padding: 12px 16px;
    }
    .work :global(.tray) {
      position: static;
      max-height: none;
    }
  }
</style>
