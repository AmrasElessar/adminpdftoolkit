"""Write THIRD_PARTY_LICENSES.md: a complete Turkish part, then a complete English part.

Same data as the in-app About & Licences page (server/adminpdf/about.py):
the hand-written server/adminpdf/about.json plus every Python package
actually installed, walked from the app's requirements. Run inside the
server's environment after changing dependencies:

    python scripts/third_party.py          # rewrite THIRD_PARTY_LICENSES.md
    python scripts/third_party.py --check  # CI: fail if it is out of date
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from adminpdf.about import curated, python_packages  # noqa: E402

OUT = ROOT / "THIRD_PARTY_LICENSES.md"

LABELS = {
    "tr": {
        "title": "Üçüncü Taraf Lisansları ve Atıflar",
        "systems": "Çalıştığı sistemler",
        "first_run": "İlk açılış uyarıları",
        "python": "Python kütüphaneleri",
        "python_intro": (
            "Uygulamanın kullandığı Python paketlerinin tamamı: önce doğrudan kullandıklarımız, sonra "
            "onların kurduğu paketler. Bu liste kurulu paketlerin kendi kayıtlarından otomatik üretilir "
            "(`python scripts/third_party.py`); uygulamadaki liste ise o pakette gerçekten kurulu olanları gösterir."
        ),
        "web": "Web arayüzü",
        "web_intro": (
            "Arayüze paketlenen npm kodunun listesi ve tam lisans metinleri her derlemede otomatik toplanır; "
            "uygulamada Hakkında ve Lisanslar penceresinde ve /licenses.txt adresinde okunur. Şu an: "
            "[Svelte](https://svelte.dev) (MIT) ve [pdf.js](https://github.com/mozilla/pdf.js) (Apache-2.0). "
            "`web/src/lib/viewer/text-layer.css`, pdf.js'in `pdf_viewer.css` dosyasının bir alt kümesidir (Apache-2.0)."
        ),
        "methods": "Yöntemler ve algoritmalar",
        "notes": "Notlar",
        "cols_pkg": "| Paket | Sürüm | Lisans | Görev / Gelen |",
        "cols_item": "| Bileşen | Lisans | Görev | Nerede |",
        "cols_method": "| Yöntem | Nerede | Kaynak |",
        "direct": "doğrudan",
        "via": "{} ile gelir",
    },
    "en": {
        "title": "Third-Party Licences and Attributions",
        "systems": "Supported systems",
        "first_run": "First-start warnings",
        "python": "Python libraries",
        "python_intro": (
            "Every Python package the app uses: first the ones we import ourselves, then what they pull in. "
            "Generated from the installed packages' own metadata (`python scripts/third_party.py`); the list "
            "inside the app shows exactly what is installed in that package."
        ),
        "web": "Web UI",
        "web_intro": (
            "The npm code bundled into the UI and its full licence texts are collected on every build and shown "
            "in the app's About & Licences window and at /licenses.txt. Currently: "
            "[Svelte](https://svelte.dev) (MIT) and [pdf.js](https://github.com/mozilla/pdf.js) (Apache-2.0). "
            "`web/src/lib/viewer/text-layer.css` is a subset of pdf.js's `pdf_viewer.css` (Apache-2.0)."
        ),
        "methods": "Methods and algorithms",
        "notes": "Notes",
        "cols_pkg": "| Package | Version | Licence | Role / Pulled in by |",
        "cols_item": "| Component | Licence | Role | Where |",
        "cols_method": "| Method | Where | Source |",
        "direct": "direct",
        "via": "via {}",
    },
}


def cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def part(lang: str, data: dict[str, Any], packages: list[dict[str, str]]) -> list[str]:
    lab = LABELS[lang]
    roles = data["python_roles"]
    out = [f"## {lab['title']}", "", data["intro"][lang], ""]
    out += [f"### {lab['systems']}", "", f"**{data['systems']['server_title'][lang]}**", ""]
    out += [f"- **{s['name'][lang]}** — {s['how'][lang]}" for s in data["systems"]["server"]]
    out += ["", f"**{data['systems']['client_title'][lang]}**", ""]
    out += [f"- **{s['name'][lang]}** — {s['how'][lang]}" for s in data["systems"]["clients"]]
    out += ["", f"### {lab['first_run']}", "", data["first_run_intro"][lang], ""]
    out += [f"- **{w['system']} — {w['title'][lang]}:** {w['steps'][lang]}" for w in data["first_run"]]
    out += ["", data["verify"][lang], ""]

    out += [f"### {lab['python']}", "", lab["python_intro"], "", lab["cols_pkg"], "|---|---|---|---|"]
    for p in packages:
        key = p["name"].lower().replace("_", "-")
        role = roles.get(key, {}).get(lang) if not p["via"] else lab["via"].format(p["via"])
        role = role or lab["direct"]
        out.append(f"| [{cell(p['name'])}]({p['url']}) | {p['version']} | {cell(p['license'])} | {cell(role)} |")
    out += ["", f"### {lab['web']}", "", lab["web_intro"], ""]

    for group in data["groups"]:
        out += [f"### {group['title'][lang]}", ""]
        if group["intro"][lang]:
            out += [group["intro"][lang], ""]
        out += [lab["cols_item"], "|---|---|---|---|"]
        for item in group["items"]:
            name = f"[{cell(item['name'])}]({item['url']})"
            role, where = cell(item["role"][lang]), cell(item["where"][lang])
            out.append(f"| {name} | {cell(item['license'])} | {role} | {where} |")
        out.append("")

    out += [f"### {lab['methods']}", "", data["methods_intro"][lang], "", lab["cols_method"], "|---|---|---|"]
    out += [f"| {cell(m['name'][lang])} | {cell(m['where'][lang])} | {cell(m['source'])} |" for m in data["methods"]]
    out += ["", f"### {lab['notes']}", ""]
    out += [f"- {n[lang]}" for n in data["notes"]]
    return [*out, ""]


def render() -> str:
    data = curated()
    packages = python_packages()
    head = [
        "# Üçüncü Taraf Lisansları / Third-Party Licences",
        "",
        "Bu dosya otomatik üretilir: `python scripts/third_party.py`. "
        "*This file is generated: `python scripts/third_party.py`.*",
        "",
        "- [Türkçe](#üçüncü-taraf-lisansları-ve-atıflar)",
        "- [English](#third-party-licences-and-attributions)",
        "",
    ]
    return "\n".join(head + part("tr", data, packages) + part("en", data, packages))


def main() -> None:
    text = render()
    if "--check" in sys.argv:
        if OUT.read_text(encoding="utf-8") != text:
            sys.exit("THIRD_PARTY_LICENSES.md is out of date: run python scripts/third_party.py")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
