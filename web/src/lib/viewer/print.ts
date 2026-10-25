import type { PDFDocumentProxy } from "./pdf";

/**
 * Print inside the app: render pages to images in a print-only container.
 * (Framing the PDF is blocked by our own `frame-ancestors 'none'` CSP.)
 */
export async function printDocument(doc: PDFDocumentProxy, onProgress: (f: number) => void): Promise<void> {
  const root = document.createElement("div");
  root.id = "print-root";
  const urls: string[] = [];
  for (let n = 1; n <= doc.numPages; n++) {
    const page = await doc.getPage(n);
    const vp = page.getViewport({ scale: 150 / 72 });
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(vp.width);
    canvas.height = Math.floor(vp.height);
    await page.render({ canvas, viewport: vp }).promise;
    const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/jpeg", 0.92));
    if (blob) {
      const url = URL.createObjectURL(blob);
      urls.push(url);
      const img = document.createElement("img");
      img.src = url;
      img.style.aspectRatio = `${vp.width} / ${vp.height}`;
      root.append(img);
    }
    page.cleanup();
    onProgress(n / doc.numPages);
  }
  document.body.append(root);
  await Promise.all([...root.querySelectorAll("img")].map((i) => i.decode().catch(() => {})));
  const cleanup = () => {
    root.remove();
    urls.forEach((u) => URL.revokeObjectURL(u));
    window.removeEventListener("afterprint", cleanup);
  };
  window.addEventListener("afterprint", cleanup);
  window.print();
  // Some browsers never fire afterprint; don't keep the images forever.
  setTimeout(cleanup, 60_000);
}
