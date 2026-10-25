import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { fileUrl } from "../api";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

export type PDFDocumentProxy = pdfjs.PDFDocumentProxy;
export type PDFPageProxy = pdfjs.PDFPageProxy;
export type PageViewport = pdfjs.PageViewport;
export { pdfjs };

export class PasswordNeeded extends Error {
  constructor(public incorrect: boolean) {
    super(incorrect ? "incorrect password" : "password required");
  }
}

/** Open a stored file with pdf.js. Throws PasswordNeeded for encrypted files. */
export async function openDocument(fileId: string, password = ""): Promise<PDFDocumentProxy> {
  const task = pdfjs.getDocument({
    url: fileUrl(fileId, true),
    password: password || undefined,
    cMapUrl: "/pdfjs/cmaps/",
    cMapPacked: true,
    standardFontDataUrl: "/pdfjs/standard_fonts/",
    wasmUrl: "/pdfjs/wasm/",
    iccUrl: "/pdfjs/iccs/",
    enableXfa: false,
  });
  try {
    return await task.promise;
  } catch (e) {
    // PasswordException isn't exported; identify it by name.
    const err = e as { name?: string; code?: number };
    if (err.name === "PasswordException") {
      throw new PasswordNeeded(err.code === pdfjs.PasswordResponses.INCORRECT_PASSWORD);
    }
    throw e;
  }
}

/** Axis-aligned rect between two viewport points, as PDF user space. */
export function viewportRectToPdf(vp: PageViewport, x0: number, y0: number, x1: number, y1: number): [number, number, number, number] {
  const [ax, ay] = vp.convertToPdfPoint(x0, y0) as [number, number];
  const [bx, by] = vp.convertToPdfPoint(x1, y1) as [number, number];
  return [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)];
}

/** PDF user-space rect → viewport CSS box {left, top, width, height}. */
export function pdfRectToViewport(vp: PageViewport, r: readonly number[]): { left: number; top: number; width: number; height: number } {
  const [x0, y0, x1, y1] = vp.convertToViewportRectangle([r[0]!, r[1]!, r[2]!, r[3]!]) as [number, number, number, number];
  return { left: Math.min(x0, x1), top: Math.min(y0, y1), width: Math.abs(x1 - x0), height: Math.abs(y1 - y0) };
}
