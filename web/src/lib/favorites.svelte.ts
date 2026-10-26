// Tools the user pinned for quick access. Per browser, like the language.
const KEY = "apt.favorites";

function initial(): string[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    if (Array.isArray(saved)) return saved.filter((n): n is string => typeof n === "string");
  } catch {
    // storage unavailable or corrupt — start empty
  }
  return [];
}

export const favorites = $state<{ names: string[] }>({ names: initial() });

export function isFavorite(name: string): boolean {
  return favorites.names.includes(name);
}

export function toggleFavorite(name: string): void {
  favorites.names = isFavorite(name) ? favorites.names.filter((n) => n !== name) : [...favorites.names, name];
  try {
    localStorage.setItem(KEY, JSON.stringify(favorites.names));
  } catch {
    // ignore
  }
}
