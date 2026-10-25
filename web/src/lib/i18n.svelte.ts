export type Lang = "tr" | "en";
export type Text = { tr: string; en: string };

function initial(): Lang {
  try {
    const saved = localStorage.getItem("apt.lang");
    if (saved === "tr" || saved === "en") return saved;
  } catch {
    // storage unavailable (private mode) — fall through
  }
  return navigator.language.toLowerCase().startsWith("tr") ? "tr" : "en";
}

export const i18n = $state<{ lang: Lang }>({ lang: initial() });

export function setLang(lang: Lang): void {
  i18n.lang = lang;
  document.documentElement.lang = lang;
  try {
    localStorage.setItem("apt.lang", lang);
  } catch {
    // ignore
  }
}

/** Pick the current-language string: `t("Kaydet", "Save")` or `t({tr, en})`. */
export function t(tr: string | Text, en?: string): string {
  if (typeof tr === "object") return tr[i18n.lang];
  return i18n.lang === "tr" ? tr : (en ?? tr);
}

export function formatBytes(n: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toLocaleString(i18n.lang === "tr" ? "tr-TR" : "en-US", { maximumFractionDigits: i ? 1 : 0 })} ${units[i]}`;
}
