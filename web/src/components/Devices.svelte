<script lang="ts">
  import { getDevices, type DeviceInfo } from "../lib/api";
  import { t } from "../lib/i18n.svelte";

  let { open = $bindable(false) }: { open: boolean } = $props();

  let dialog: HTMLDialogElement;
  let info = $state<DeviceInfo | null>(null);
  let failed = $state(false);
  let copied = $state(-1);

  $effect(() => {
    if (open && !dialog.open) {
      dialog.showModal();
      failed = false;
      getDevices()
        .then((d) => (info = d))
        .catch(() => (failed = true));
    } else if (!open && dialog.open) dialog.close();
  });

  async function copy(i: number, url: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(url);
      copied = i;
      setTimeout(() => (copied = -1), 1500);
    } catch {
      // clipboard blocked — the link is selectable text anyway
    }
  }

  const short = (fp: string) => fp.slice(0, 23);
</script>

<dialog bind:this={dialog} onclose={() => (open = false)} aria-labelledby="dev-title">
  <header>
    <h2 id="dev-title">{t("Telefon / tablet bağla", "Connect a phone / tablet")}</h2>
    <button class="icon" onclick={() => dialog.close()} aria-label={t("Kapat", "Close")}>✕</button>
  </header>

  {#if failed}
    <p class="error">{t("Bilgi alınamadı.", "Could not load the details.")}</p>
  {:else if !info}
    <p class="muted">{t("Yükleniyor…", "Loading…")}</p>
  {:else if !info.lan_enabled}
    <p>
      {t(
        "Ağ paylaşımı kapalı. Uygulamayı “Başlat - Ağ Paylaşımı” ile (veya python -m adminpdf --lan) başlatın; burada her cihaz için bir QR kod görünür.",
        "Network sharing is off. Start the app with “Start - Network Sharing” (or python -m adminpdf --lan); a QR code for devices then appears here.",
      )}
    </p>
    <p class="muted small">
      {t(
        "Yalnızca aynı yerel ağdaki cihazlar bağlanabilir; internetten erişim her zaman kapalıdır.",
        "Only devices on the same local network can connect; access from the internet is always blocked.",
      )}
    </p>
  {:else if !info.urls.length}
    <p>
      {t(
        "Bu bilgisayarın yerel ağ adresi bulunamadı. Wi-Fi / kablo bağlantısını kontrol edin.",
        "No local-network address was found for this computer. Check the Wi-Fi / cable connection.",
      )}
    </p>
  {:else}
    <div class="links">
      {#each info.urls as url, i (url)}
        <figure>
          <img src={`/api/session/devices/qr.svg?i=${i}`} alt={t("Eşleştirme QR kodu", "Pairing QR code")} width="220" height="220" />
          <figcaption>
            <code>{url.replace(/#pair=.*/, "")}</code>
            <button class="small ghost" onclick={() => copy(i, url)}>
              {copied === i ? t("Kopyalandı ✓", "Copied ✓") : t("Bağlantıyı kopyala", "Copy link")}
            </button>
          </figcaption>
        </figure>
      {/each}
    </div>
    <ol>
      <li>{t("Telefon veya tabletin kamerasıyla QR kodu okutun.", "Scan the QR code with the phone or tablet camera.")}</li>
      {#if info.tls}
        <li>
          {t(
            "Tarayıcı ilk seferde sertifika uyarısı gösterir. Uyarısız ve en güvenli kullanım için eşleştirme ekranındaki “Sertifikayı yükle” bağlantısıyla bu sunucunun sertifikasını bir kez yükleyin.",
            "The browser warns about the certificate the first time. For warning-free, safest use, install this server's certificate once via “Install certificate” on the pairing screen.",
          )}
        </li>
      {/if}
      <li>{t("Eşleşme otomatik yapılır; cihaz 30 gün hatırlanır.", "Pairing happens automatically; the device is remembered for 30 days.")}</li>
    </ol>
    {#if info.fingerprint}
      <p class="fp">
        <strong>{t("Sertifika parmak izi (SHA-256)", "Certificate fingerprint (SHA-256)")}</strong>
        <span>{t("Cihazda sertifikayı yüklerken bunun ilk kısmıyla karşılaştırın:", "Compare its start when installing the certificate on the device:")}</span>
        <code title={info.fingerprint}>{short(info.fingerprint)}…</code>
      </p>
    {/if}
    <p class="muted small">
      {t(
        "Bu QR kod eşleştirme anahtarını içerir: yalnızca güvendiğiniz kişilere gösterin.",
        "This QR code contains the pairing key: show it only to people you trust.",
      )}
    </p>
  {/if}
</dialog>

<style>
  dialog {
    width: min(640px, calc(100vw - 32px));
    max-height: calc(100dvh - 48px);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text);
    padding: 18px 20px;
  }
  dialog::backdrop {
    background: rgb(0 0 0 / 0.4);
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  h2 {
    margin: 0;
    font-size: 1.15rem;
  }
  .links {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    justify-content: center;
    margin: 14px 0 6px;
  }
  figure {
    display: grid;
    gap: 8px;
    justify-items: center;
    margin: 0;
  }
  figure img {
    width: 220px;
    height: 220px;
    border-radius: 10px;
    background: #fff;
    image-rendering: pixelated;
  }
  figcaption {
    display: grid;
    gap: 6px;
    justify-items: center;
  }
  code {
    font-size: 0.85rem;
    word-break: break-all;
  }
  ol {
    margin: 8px 0;
    padding-left: 20px;
    display: grid;
    gap: 4px;
    font-size: 0.9rem;
  }
  .fp {
    display: grid;
    gap: 2px;
    padding: 8px 10px;
    border-radius: 10px;
    background: var(--surface-2);
    font-size: 0.85rem;
  }
  .fp span {
    color: var(--muted);
  }
  .small {
    font-size: 0.8rem;
  }
  .muted {
    color: var(--muted);
  }
  .error {
    color: var(--danger);
  }
</style>
