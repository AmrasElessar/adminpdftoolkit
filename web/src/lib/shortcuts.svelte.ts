import type { Text } from "./i18n.svelte";

export const ui = $state({ showShortcuts: false });

export interface Shortcut {
  keys: string[];
  label: Text;
}

export const SHORTCUTS: { title: Text; items: Shortcut[] }[] = [
  {
    title: { tr: "Genel", en: "General" },
    items: [
      { keys: ["Ctrl", "O"], label: { tr: "Dosya aç / yükle", en: "Open / upload files" } },
      { keys: ["/"], label: { tr: "Araç ara", en: "Search tools" } },
      { keys: ["Esc"], label: { tr: "Geri / kapat", en: "Back / close" } },
      { keys: ["Ctrl", "Enter"], label: { tr: "Araç formunu çalıştır", en: "Run the tool form" } },
      { keys: ["?"], label: { tr: "Bu kısayol listesi", en: "This shortcut list" } },
    ],
  },
  {
    title: { tr: "Görüntüleyici", en: "Viewer" },
    items: [
      { keys: ["Alt", "1"], label: { tr: "Görüntüle modu", en: "View mode" } },
      { keys: ["Alt", "2"], label: { tr: "Sayfalar modu", en: "Pages mode" } },
      { keys: ["Alt", "3"], label: { tr: "Düzenle modu", en: "Edit mode" } },
      { keys: ["Alt", "4"], label: { tr: "KVKK modu (tara ve uygula)", en: "Personal-data mode (scan & apply)" } },
      { keys: ["Ctrl", "F"], label: { tr: "Belgede ara", en: "Find in document" } },
      { keys: ["Enter"], label: { tr: "Sonraki eşleşme (aramada)", en: "Next match (in search)" } },
      { keys: ["Ctrl", "P"], label: { tr: "Yazdır", en: "Print" } },
      { keys: ["PgDn", "PgUp"], label: { tr: "Sonraki / önceki sayfa", en: "Next / previous page" } },
      { keys: ["Home", "End"], label: { tr: "İlk / son sayfa", en: "First / last page" } },
      { keys: ["Ctrl", "+"], label: { tr: "Yakınlaştır", en: "Zoom in" } },
      { keys: ["Ctrl", "−"], label: { tr: "Uzaklaştır", en: "Zoom out" } },
      { keys: ["Ctrl", "0"], label: { tr: "Genişliğe sığdır", en: "Fit width" } },
    ],
  },
  {
    title: { tr: "Editör", en: "Editor" },
    items: [
      { keys: ["V"], label: { tr: "Seç / taşı", en: "Select / move" } },
      { keys: ["E"], label: { tr: "Metni düzenle", en: "Edit text" } },
      { keys: ["T"], label: { tr: "Metin ekle", en: "Add text" } },
      { keys: ["H"], label: { tr: "Vurgula", en: "Highlight" } },
      { keys: ["U"], label: { tr: "Altını çiz", en: "Underline" } },
      { keys: ["K"], label: { tr: "Üstünü çiz", en: "Strikethrough" } },
      { keys: ["N"], label: { tr: "Not", en: "Note" } },
      { keys: ["D"], label: { tr: "Kalem (serbest çizim)", en: "Pen (freehand)" } },
      { keys: ["R"], label: { tr: "Dikdörtgen", en: "Rectangle" } },
      { keys: ["O"], label: { tr: "Elips", en: "Ellipse" } },
      { keys: ["L"], label: { tr: "Çizgi", en: "Line" } },
      { keys: ["A"], label: { tr: "Ok", en: "Arrow" } },
      { keys: ["W"], label: { tr: "Beyazla kapat", en: "Whiteout" } },
      { keys: ["I"], label: { tr: "Görsel ekle", en: "Insert image" } },
      { keys: ["S"], label: { tr: "İmza", en: "Signature" } },
      { keys: ["G"], label: { tr: "Bağlantı", en: "Link" } },
      { keys: ["F"], label: { tr: "Form alanı", en: "Form field" } },
      { keys: ["Ctrl", "S"], label: { tr: "Kaydet", en: "Save" } },
      { keys: ["Ctrl", "Z"], label: { tr: "Geri al", en: "Undo" } },
      { keys: ["Ctrl", "Y"], label: { tr: "Yinele (Ctrl+Shift+Z)", en: "Redo (Ctrl+Shift+Z)" } },
      { keys: ["Del"], label: { tr: "Seçileni sil", en: "Delete selection" } },
      { keys: ["←", "→", "↑", "↓"], label: { tr: "Seçileni 1 pt taşı (Shift: 10 pt)", en: "Nudge 1 pt (Shift: 10 pt)" } },
      { keys: ["Ctrl", "Enter"], label: { tr: "Metin kutusunu bitir", en: "Finish text box" } },
      { keys: ["Esc"], label: { tr: "Seçimi bırak, Seç aracına dön", en: "Deselect, back to Select" } },
    ],
  },
];

/** True when the key event comes from a text-entry control. */
export function typing(e: KeyboardEvent): boolean {
  const el = e.target as HTMLElement | null;
  return !!el?.closest("input, textarea, select, [contenteditable]");
}
