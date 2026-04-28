/* ===========================================================================
 * HT Admin PDF Editor — Phases 4a (viewer) + 4b (annotation modes)
 * ---------------------------------------------------------------------------
 * Architecture
 *   • Two stacked canvases inside #peCanvasWrap:
 *       - peCanvas (bottom): pdf.js renders the page bitmap here.
 *       - peOverlayCanvas (top): we draw live previews + persisted operations
 *         on this layer. Mouse events fire on the overlay only.
 *   • editState.opsByPage: Map<pageIdx, op[]> — operations the user has
 *     queued. Saved as a flat list to /pdf/edit/save when the user hits Save.
 *   • All coordinates we send to the backend are in PDF points (top-left
 *     origin). Conversion: pdf_pt = canvas_px / scale.
 *
 * Modes (4b)
 *   - "highlight" / "underline" / "strikeout": click-and-drag rect
 *   - "sticky":   click → prompt for content
 *   - "ink":      free draw (mousedown → mousemove path → mouseup)
 *   - "image":    pick PNG/JPG → click-and-drag rect to place
 *
 * What's still pending (4c / 4d):
 *   - Add new text overlay (4c)
 *   - Replace existing text with smart font matching (4d)
 *
 * Notes on i18n
 *   • Every user-visible string is written in Turkish; i18n.js translates
 *     them via STRINGS / PATTERNS dictionaries when EN is active.
 * =========================================================================== */

const PDFJS_URL = "/static/pdfjs/pdf.min.mjs";
const PDFJS_WORKER_URL = "/static/pdfjs/pdf.worker.min.mjs";
const FONTS_ENDPOINT = "/pdf/edit/fonts";
const SAVE_ENDPOINT = "/pdf/edit/save";
const SPANS_ENDPOINT = "/pdf/edit/spans";

const editState = {
  file: null,
  doc: null,
  pageNo: 1,
  pageTotal: 0,
  scale: 1.0,
  dpr: 1,                        // device pixel ratio for hi-DPI rendering
  mode: "view",                  // view | highlight | underline | strikeout | sticky | ink | image | text | rect | ellipse | line | replace
  opsByPage: new Map(),          // pageNo → op[]
  pendingImageDataUrl: null,     // staged data URL for "image" mode
  spans: [],                     // replace-mode: every text span across pages
  spansLoading: false,
  hoverSpanIdx: -1,              // index of span under cursor (replace mode)
  granularity: "line",           // word | line | block — replace-mode selection
  extractability: null,          // {type, extractable, message, ...} from /pdf/edit/spans
};

let pdfjsLib = null;
let pdfjsLoadPromise = null;
let renderTask = null;

// =========================================================================
// 1. Bootstrap
// =========================================================================
async function bootEditor() {
  const back = document.getElementById("pdfEditorModalBack");
  // pdfEditorBtn header'dan kaldırıldı; modal artık dashboard kartı tarafından
  // açılıyor. Yine de varsa eski click handler'ını bağla — null olabilir.
  const openBtn = document.getElementById("pdfEditorBtn");
  if (!back) return;

  // Modal open / close
  openBtn?.addEventListener("click", openModal);
  document.getElementById("pdfEditorCancel")?.addEventListener("click", closeModal);
  back.addEventListener("click", (e) => { if (e.target === back) closeModal(); });

  // File pick
  const fileInput = document.getElementById("peFileInput");
  document.getElementById("peOpenBtn")?.addEventListener("click", () => fileInput?.click());
  document.getElementById("peEmptyOpen")?.addEventListener("click", () => fileInput?.click());
  fileInput?.addEventListener("change", async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    await loadPdf(f);
    fileInput.value = "";
  });

  // Page navigation + zoom
  document.getElementById("pePrevBtn")?.addEventListener("click", () => goToPage(editState.pageNo - 1));
  document.getElementById("peNextBtn")?.addEventListener("click", () => goToPage(editState.pageNo + 1));
  document.getElementById("peZoomInBtn")?.addEventListener("click", () => setScale(editState.scale * 1.2));
  document.getElementById("peZoomOutBtn")?.addEventListener("click", () => setScale(editState.scale / 1.2));
  document.getElementById("peZoom")?.addEventListener("change", (e) => setScale(parseFloat(e.target.value) || 1.0));

  // Top-level mode picker
  document.querySelectorAll(".pe-mode").forEach((btn) => {
    btn.addEventListener("click", () => switchTopMode(btn));
  });
  // Sub-mode picker (within "Vurgu / Not")
  document.querySelectorAll(".pe-submode").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      const sm = btn.dataset.submode;
      if (!sm) return;
      editState.mode = sm;
      setActiveSubMode(sm);
      setCursor();
      const top = document.querySelector(".pe-mode[data-mode='annot']");
      if (top) document.getElementById("peModeLabel").textContent =
        "Mod: " + (top.textContent || "").trim() + " · " + (btn.textContent || "").trim();
    });
  });
  document.getElementById("peSaveBtn")?.addEventListener("click", saveEdits);
  document.getElementById("peUndoBtn")?.addEventListener("click", undoLast);
  document.getElementById("peClearBtn")?.addEventListener("click", clearPage);

  // Replace-mode granularity radio
  document.querySelectorAll('input[name="peGranularity"]').forEach((r) => {
    r.addEventListener("change", (e) => {
      const v = e.target.value;
      if (!v || v === editState.granularity) return;
      editState.granularity = v;
      editState.spans = [];
      editState.hoverSpanIdx = -1;
      ensureSpansLoaded(true);
    });
  });

  // Mobile sidebar drawer
  document.getElementById("peBurgerBtn")?.addEventListener("click", toggleDrawer);
  document.getElementById("peShell")?.addEventListener("click", (e) => {
    // Backdrop click closes drawer
    if (e.target === e.currentTarget) closeDrawer();
  });
  // Close drawer after picking a mode on mobile (matches typical app UX)
  document.querySelectorAll(".pe-mode, .pe-submode").forEach((b) => {
    b.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 899px)").matches) closeDrawer();
    });
  });
}

function toggleDrawer() {
  const side = document.getElementById("peSide");
  const shell = document.getElementById("peShell");
  if (!side || !shell) return;
  const isShown = side.classList.toggle("shown");
  shell.classList.toggle("drawer-open", isShown);
}
function closeDrawer() {
  document.getElementById("peSide")?.classList.remove("shown");
  document.getElementById("peShell")?.classList.remove("drawer-open");
}

function openModal() {
  document.getElementById("pdfEditorModalBack")?.classList.add("shown");
  ensurePdfJs().catch((err) => setStatus("pdf.js yüklenemedi: " + (err?.message || err), "err"));
  ensureFonts();
}
function closeModal() {
  document.getElementById("pdfEditorModalBack")?.classList.remove("shown");
}

function ensurePdfJs() {
  if (pdfjsLib) return Promise.resolve(pdfjsLib);
  if (pdfjsLoadPromise) return pdfjsLoadPromise;
  pdfjsLoadPromise = import(PDFJS_URL).then((mod) => {
    pdfjsLib = mod;
    pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER_URL;
    return pdfjsLib;
  });
  return pdfjsLoadPromise;
}

let fontsLoaded = false;
let fontsCatalog = [];   // [{id, label, category, variants: ["regular","bold",...]}, ...]
async function ensureFonts() {
  if (fontsLoaded) return;
  try {
    const r = await fetch(FONTS_ENDPOINT);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const sel = document.getElementById("peFontFamily");
    if (sel && Array.isArray(data.families)) {
      sel.innerHTML = data.families.map((f) =>
        `<option value="${f.id}">${f.label}</option>`).join("");
      sel.addEventListener("change", refreshBoldItalicAvailability);
      fontsCatalog = data.families;
      refreshBoldItalicAvailability();
    }
    fontsLoaded = true;
  } catch (e) {
    setStatus("Yazı tipi listesi alınamadı — varsayılan kullanılacak.", "err");
  }
}

function refreshBoldItalicAvailability() {
  const sel = document.getElementById("peFontFamily");
  const familyId = sel?.value;
  const family = fontsCatalog.find((f) => f.id === familyId);
  const variants = new Set(family?.variants || ["regular"]);
  const boldEl = document.getElementById("peFontBold");
  const italEl = document.getElementById("peFontItalic");
  if (boldEl) {
    boldEl.disabled = !(variants.has("bold") || variants.has("bolditalic"));
    if (boldEl.disabled) boldEl.checked = false;
  }
  if (italEl) {
    italEl.disabled = !(variants.has("italic") || variants.has("bolditalic"));
    if (italEl.disabled) italEl.checked = false;
  }
}

// =========================================================================
// 2. Document load + page render
// =========================================================================
async function loadPdf(file) {
  setStatus("pdf.js yükleniyor…");
  try {
    await ensurePdfJs();
    setStatus("Dosya okunuyor…");
    const buf = await file.arrayBuffer();
    setStatus("PDF açılıyor…");
    const doc = await pdfjsLib.getDocument({ data: buf }).promise;
    editState.file = file;
    editState.doc = doc;
    editState.pageTotal = doc.numPages;
    editState.pageNo = 1;
    editState.opsByPage = new Map();
    editState.spans = [];
    pendingImageDataUrl();  // reset
    document.getElementById("pePageTotal").textContent = String(doc.numPages);
    document.getElementById("peDocInfo").textContent =
      file.name + " · " + doc.numPages + " sayfa · " + Math.round(file.size / 1024) + " KB";
    document.getElementById("peEmpty").style.display = "none";
    const stack = document.getElementById("peStack");
    if (stack) stack.style.display = "";
    ensureOverlay();
    setNavEnabled(true);
    enableModes(true);
    setStatus("Sayfa render ediliyor…");
    await renderPage(1);
    setStatus("Hazır.", "ok");
    refreshSaveButton();
  } catch (err) {
    console.error("[pdf-editor] loadPdf failed:", err);
    setStatus("PDF açılamadı: " + (err?.message || err), "err");
  }
}

async function renderPage(n) {
  if (!editState.doc) return;
  if (n < 1 || n > editState.pageTotal) return;
  if (renderTask) {
    try { renderTask.cancel(); } catch (e) { /* noop */ }
    renderTask = null;
  }
  // Hi-DPI: render bitmap at devicePixelRatio × scale so canvas stays crisp
  // on Retina / 4K. CSS dimensions match "scale ×" only — display size
  // doesn't change. Cap at 3 for memory sanity on cheap GPUs.
  const dpr = Math.min(3, window.devicePixelRatio || 1);
  editState.dpr = dpr;
  const page = await editState.doc.getPage(n);
  const cssViewport = page.getViewport({ scale: editState.scale });
  const renderViewport = page.getViewport({ scale: editState.scale * dpr });
  const canvas = document.getElementById("peCanvas");
  const ctx = canvas.getContext("2d");
  canvas.width = Math.ceil(renderViewport.width);
  canvas.height = Math.ceil(renderViewport.height);
  canvas.style.width = Math.ceil(cssViewport.width) + "px";
  canvas.style.height = Math.ceil(cssViewport.height) + "px";
  renderTask = page.render({ canvasContext: ctx, viewport: renderViewport });
  try {
    await renderTask.promise;
  } catch (err) {
    if (err?.name !== "RenderingCancelledException") throw err;
  } finally {
    renderTask = null;
  }
  editState.pageNo = n;
  document.getElementById("pePageNo").textContent = String(n);
  syncOverlayToCanvas();
  redrawOverlay();
}

function goToPage(n) {
  if (!editState.doc) return;
  const target = Math.max(1, Math.min(editState.pageTotal, n));
  if (target === editState.pageNo) return;
  renderPage(target);
}

function setScale(s) {
  const clamped = Math.max(0.25, Math.min(4.0, s));
  editState.scale = clamped;
  const zoom = document.getElementById("peZoom");
  if (zoom) {
    const presets = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];
    let nearest = 1.0, best = Infinity;
    for (const p of presets) {
      const d = Math.abs(p - clamped);
      if (d < best) { best = d; nearest = p; }
    }
    zoom.value = String(nearest);
  }
  if (editState.doc) renderPage(editState.pageNo);
}

// =========================================================================
// 3. Overlay canvas — drawing + mouse handlers
// =========================================================================
let _overlayWired = false;
function ensureOverlay() {
  // peOverlayCanvas now lives in HTML alongside peCanvas inside #peStack;
  // we just need to wire mouse + touch events once.
  const overlay = document.getElementById("peOverlayCanvas");
  if (!overlay) return null;
  if (!_overlayWired) {
    overlay.addEventListener("mousedown", onOverlayMouseDown);
    overlay.addEventListener("mousemove", onOverlayMouseMove);
    overlay.addEventListener("mouseup", onOverlayMouseUp);
    overlay.addEventListener("mouseleave", onOverlayMouseUp);
    overlay.addEventListener("touchstart", onTouchStart, { passive: false });
    overlay.addEventListener("touchmove", onTouchMove, { passive: false });
    overlay.addEventListener("touchend", onTouchEnd);
    _overlayWired = true;
  }
  return overlay;
}

function syncOverlayToCanvas() {
  const base = document.getElementById("peCanvas");
  const overlay = ensureOverlay();
  if (!base || !overlay) return;
  // Overlay's bitmap matches base's bitmap (same dpr-scaled resolution).
  // Both canvases share the same CSS dimensions = base.style.width/height.
  overlay.width = base.width;
  overlay.height = base.height;
  overlay.style.width = base.style.width;
  overlay.style.height = base.style.height;
  // peStack matches CSS dimensions so the scroll container measures correctly
  const stack = document.getElementById("peStack");
  if (stack) {
    stack.style.width = base.style.width;
    stack.style.height = base.style.height;
  }
}

let dragState = null;     // {x0, y0, x1, y1}
let inkStrokes = [];      // current ink: list of strokes; each stroke = list of [x,y]
let inkActive = false;

function setCursor() {
  const overlay = document.getElementById("peOverlayCanvas");
  if (!overlay) return;
  const cursorMap = {
    view: "default",
    highlight: "crosshair",
    underline: "crosshair",
    strikeout: "crosshair",
    sticky: "pointer",
    ink: "crosshair",
    image: "copy",
    text: "text",
    rect: "crosshair",
    ellipse: "crosshair",
    line: "crosshair",
  };
  overlay.style.cursor = cursorMap[editState.mode] || "default";
}

function localPos(evt) {
  const overlay = document.getElementById("peOverlayCanvas");
  const rect = overlay.getBoundingClientRect();
  const cx = (evt.clientX !== undefined ? evt.clientX : evt.touches?.[0]?.clientX) - rect.left;
  const cy = (evt.clientY !== undefined ? evt.clientY : evt.touches?.[0]?.clientY) - rect.top;
  const sx = overlay.width / rect.width;
  const sy = overlay.height / rect.height;
  return { x: cx * sx, y: cy * sy };
}

function onOverlayMouseDown(evt) {
  if (editState.mode === "view" || !editState.doc) return;
  evt.preventDefault();
  const pos = localPos(evt);

  if (editState.mode === "sticky") {
    const content = window.prompt(_t("Not içeriği:"), "");
    if (content && content.trim()) {
      const op = {
        type: "sticky",
        page: editState.pageNo,
        point: canvasToPdf(pos.x, pos.y),
        content: content.trim(),
        color: [1.0, 0.85, 0.0],
      };
      pushOp(op);
      redrawOverlay();
    }
    return;
  }

  if (editState.mode === "ink") {
    inkActive = true;
    inkStrokes = [[ [pos.x, pos.y] ]];
    drawCurrentInk();
    return;
  }

  if (editState.mode === "image") {
    if (!editState.pendingImageDataUrl) {
      pickImageThen(() => { /* user can now drag a rect */ });
      return;
    }
    dragState = { x0: pos.x, y0: pos.y, x1: pos.x, y1: pos.y };
    return;
  }

  if (editState.mode === "text") {
    // Click → drop a textarea editor at this point
    spawnTextEditor(pos.x, pos.y);
    return;
  }

  if (editState.mode === "replace") {
    const hit = findSpanAtCanvas(pos.x, pos.y);
    if (hit) spawnReplaceEditor(hit.span);
    return;
  }

  // highlight / underline / strikeout / rect / ellipse / line — drag-based
  dragState = { x0: pos.x, y0: pos.y, x1: pos.x, y1: pos.y };
}

function onOverlayMouseMove(evt) {
  if (!editState.doc) return;
  const pos = localPos(evt);
  if (editState.mode === "ink" && inkActive) {
    inkStrokes[inkStrokes.length - 1].push([pos.x, pos.y]);
    drawCurrentInk();
    return;
  }
  if (editState.mode === "replace") {
    const hit = findSpanAtCanvas(pos.x, pos.y);
    const spans = currentPageSpans();
    const newIdx = hit ? spans.indexOf(hit.span) : -1;
    if (newIdx !== editState.hoverSpanIdx) {
      editState.hoverSpanIdx = newIdx;
      redrawOverlay();
    }
    return;
  }
  if (dragState) {
    dragState.x1 = pos.x;
    dragState.y1 = pos.y;
    redrawOverlay();
    drawDragPreview();
  }
}

function onOverlayMouseUp(_evt) {
  if (!editState.doc) return;
  if (editState.mode === "ink" && inkActive) {
    inkActive = false;
    if (inkStrokes[0]?.length >= 2) {
      const op = {
        type: "ink",
        page: editState.pageNo,
        strokes: inkStrokes.map((s) => s.map(([x, y]) => canvasToPdfPair(x, y))),
        color: hexToRgb(getColor()),
        stroke_width: 1.5,
      };
      pushOp(op);
    }
    inkStrokes = [];
    redrawOverlay();
    return;
  }
  if (!dragState) return;
  const { x0, y0, x1, y1 } = dragState;
  dragState = null;
  // Lines need a longer minimum length than rects; both filter out clicks
  const minLen = editState.mode === "line" ? 6 : 4;
  if (editState.mode === "line") {
    const dx = x1 - x0, dy = y1 - y0;
    if (Math.hypot(dx, dy) < minLen) {
      redrawOverlay();
      return;
    }
    pushOp({
      type: "line",
      page: editState.pageNo,
      p1: canvasToPdfPair(x0, y0),
      p2: canvasToPdfPair(x1, y1),
      color: hexToRgb(getColor()),
      stroke_width: 1.5,
    });
    redrawOverlay();
    return;
  }
  if (Math.abs(x1 - x0) < minLen || Math.abs(y1 - y0) < minLen) {
    redrawOverlay();
    return;
  }
  const rect = canvasRectToPdf(x0, y0, x1, y1);
  if (editState.mode === "image") {
    if (!editState.pendingImageDataUrl) { redrawOverlay(); return; }
    pushOp({
      type: "image",
      page: editState.pageNo,
      rect,
      image_data_url: editState.pendingImageDataUrl,
    });
  } else if (editState.mode === "rect" || editState.mode === "ellipse") {
    pushOp({
      type: editState.mode,
      page: editState.pageNo,
      rect,
      color: hexToRgb(getColor()),
      stroke_width: 1.5,
    });
  } else {
    // highlight / underline / strikeout
    pushOp({
      type: editState.mode,
      page: editState.pageNo,
      rect,
      color: hexToRgb(getColor()),
    });
  }
  redrawOverlay();
}

// Touch shims — single-finger drawing only
function onTouchStart(e) { e.preventDefault(); onOverlayMouseDown(e); }
function onTouchMove(e)  { e.preventDefault(); onOverlayMouseMove(e); }
function onTouchEnd(e)   { onOverlayMouseUp(e); }

// =========================================================================
// 4. Coordinate conversion + drawing helpers
//
// Canvas bitmap is sized at scale × dpr (hi-DPI crispness). Mouse events
// reach us in the same bitmap-pixel space (localPos already accounts for
// the CSS↔bitmap ratio). PDF points are bitmap_px / (scale × dpr).
// =========================================================================
function _bitmapPerPoint() {
  return editState.scale * (editState.dpr || 1);
}
function canvasToPdfPair(cx, cy) {
  const k = _bitmapPerPoint();
  return [cx / k, cy / k];
}
function canvasToPdf(cx, cy) {
  return canvasToPdfPair(cx, cy);
}
function canvasRectToPdf(x0, y0, x1, y1) {
  const a = canvasToPdfPair(x0, y0);
  const b = canvasToPdfPair(x1, y1);
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])];
}
function pdfRectToCanvas(rect) {
  const k = _bitmapPerPoint();
  return [rect[0] * k, rect[1] * k, rect[2] * k, rect[3] * k];
}
function pdfPointToCanvas(point) {
  const k = _bitmapPerPoint();
  return [point[0] * k, point[1] * k];
}

function getColor() {
  return document.getElementById("peFontColor")?.value || "#FFEB3B";
}
function hexToRgb(hex) {
  const m = /^#?([a-f0-9]{2})([a-f0-9]{2})([a-f0-9]{2})$/i.exec(hex || "");
  if (!m) return [0, 0, 0];
  return [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255];
}
function rgbToCss(rgb) {
  return `rgb(${Math.round(rgb[0] * 255)},${Math.round(rgb[1] * 255)},${Math.round(rgb[2] * 255)})`;
}

function redrawOverlay() {
  const overlay = document.getElementById("peOverlayCanvas");
  if (!overlay) return;
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  const ops = editState.opsByPage.get(editState.pageNo) || [];
  for (const op of ops) drawOpPreview(ctx, op);

  // Replace mode: paint span outlines so user knows what's clickable
  if (editState.mode === "replace") {
    const spans = currentPageSpans();
    spans.forEach((span, i) => {
      const [x0, y0, x1, y1] = pdfRectToCanvas(span.rect);
      ctx.strokeStyle = (i === editState.hoverSpanIdx) ? "#2F5496" : "rgba(47,84,150,0.35)";
      ctx.lineWidth = (i === editState.hoverSpanIdx) ? 1.5 : 1;
      ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      if (i === editState.hoverSpanIdx) {
        ctx.fillStyle = "rgba(47,84,150,0.08)";
        ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
      }
    });
  }
}

function currentPageSpans() {
  return editState.spans.filter((s) => s.page === editState.pageNo);
}

function findSpanAtCanvas(cx, cy) {
  const [px, py] = canvasToPdfPair(cx, cy);
  const spans = currentPageSpans();
  // Iterate in reverse so the topmost (last-drawn) span wins on overlap
  for (let i = spans.length - 1; i >= 0; i--) {
    const r = spans[i].rect;
    if (px >= r[0] && px <= r[2] && py >= r[1] && py <= r[3]) {
      return { span: spans[i], indexInPage: i };
    }
  }
  return null;
}

function drawOpPreview(ctx, op) {
  const color = op.color ? rgbToCss(op.color) : "#FFEB3B";
  if (op.type === "replace" && op.rect) {
    const [x0, y0, x1, y1] = pdfRectToCanvas(op.rect);
    // Red strikethrough across the original span area
    ctx.fillStyle = "rgba(220, 38, 38, 0.18)";
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    ctx.setLineDash([]);
    // Cross out original
    ctx.beginPath();
    ctx.moveTo(x0, (y0 + y1) / 2);
    ctx.lineTo(x1, (y0 + y1) / 2);
    ctx.stroke();
    // Annotated label: "→ new text"
    if (op.text) {
      const sizePx = (op.fontsize || 11) * _bitmapPerPoint();
      const fontSpec = (op.italic ? "italic " : "") + (op.bold ? "bold " : "") +
        sizePx + "px " + cssFamilyForId(op.font_id || "noto-sans");
      ctx.font = fontSpec;
      ctx.fillStyle = op.color ? rgbToCss(op.color) : "#1f3a6e";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(op.text, x0, y1 - sizePx * 0.15);
    }
    return;
  }
  if (op.type === "text" && op.point) {
    const [x, y] = pdfPointToCanvas(op.point);
    const sizePx = (op.fontsize || 12) * _bitmapPerPoint();
    const fontSpec = (op.italic ? "italic " : "") + (op.bold ? "bold " : "") +
      sizePx + "px " + cssFamilyForId(op.font_id);
    ctx.font = fontSpec;
    ctx.fillStyle = color;
    ctx.textBaseline = "top";
    ctx.fillText(op.text || "", x, y);
    return;
  }
  if (op.type === "rect" && op.rect) {
    const [x0, y0, x1, y1] = pdfRectToCanvas(op.rect);
    ctx.strokeStyle = color;
    ctx.lineWidth = (op.stroke_width || 1.0) * _bitmapPerPoint();
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    if (op.fill) {
      ctx.fillStyle = rgbToCss(op.fill);
      ctx.globalAlpha = 0.4;
      ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
      ctx.globalAlpha = 1.0;
    }
    return;
  }
  if (op.type === "ellipse" && op.rect) {
    const [x0, y0, x1, y1] = pdfRectToCanvas(op.rect);
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const rx = Math.abs(x1 - x0) / 2, ry = Math.abs(y1 - y0) / 2;
    ctx.strokeStyle = color;
    ctx.lineWidth = (op.stroke_width || 1.0) * _bitmapPerPoint();
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.stroke();
    if (op.fill) {
      ctx.fillStyle = rgbToCss(op.fill);
      ctx.globalAlpha = 0.4;
      ctx.fill();
      ctx.globalAlpha = 1.0;
    }
    return;
  }
  if (op.type === "line" && op.p1 && op.p2) {
    const [x1, y1] = pdfPointToCanvas(op.p1);
    const [x2, y2] = pdfPointToCanvas(op.p2);
    ctx.strokeStyle = color;
    ctx.lineWidth = (op.stroke_width || 1.5) * _bitmapPerPoint();
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    return;
  }
  if (op.type === "highlight" && op.rect) {
    const [x0, y0, x1, y1] = pdfRectToCanvas(op.rect);
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.4;
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.globalAlpha = 1.0;
  } else if (op.type === "underline" && op.rect) {
    const [x0, , x1, y1] = pdfRectToCanvas(op.rect);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x0, y1 - 1);
    ctx.lineTo(x1, y1 - 1);
    ctx.stroke();
  } else if (op.type === "strikeout" && op.rect) {
    const [x0, y0, x1, y1] = pdfRectToCanvas(op.rect);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    const my = (y0 + y1) / 2;
    ctx.moveTo(x0, my);
    ctx.lineTo(x1, my);
    ctx.stroke();
  } else if (op.type === "sticky" && op.point) {
    const [x, y] = pdfPointToCanvas(op.point);
    ctx.fillStyle = color;
    ctx.fillRect(x - 8, y - 8, 16, 16);
    ctx.strokeStyle = "#1f3a6e";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(x - 8, y - 8, 16, 16);
    ctx.fillStyle = "#1f3a6e";
    ctx.font = "bold 11px sans-serif";
    ctx.fillText("✎", x - 4, y + 4);
  } else if (op.type === "ink" && op.strokes) {
    const k = _bitmapPerPoint();
    ctx.strokeStyle = color;
    ctx.lineWidth = (op.stroke_width || 1.5) * k;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const stroke of op.strokes) {
      ctx.beginPath();
      stroke.forEach(([x, y], i) => {
        const cx = x * k;
        const cy = y * k;
        if (i === 0) ctx.moveTo(cx, cy);
        else ctx.lineTo(cx, cy);
      });
      ctx.stroke();
    }
  } else if (op.type === "image" && op.rect) {
    const [x0, y0, x1, y1] = pdfRectToCanvas(op.rect);
    ctx.fillStyle = "rgba(47,84,150,0.2)";
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.strokeStyle = "#2F5496";
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 1.5;
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    ctx.setLineDash([]);
    ctx.fillStyle = "#2F5496";
    ctx.font = "11px sans-serif";
    ctx.fillText("🖼", x0 + 4, y0 + 14);
  }
}

function drawDragPreview() {
  const overlay = document.getElementById("peOverlayCanvas");
  if (!overlay || !dragState) return;
  const ctx = overlay.getContext("2d");
  const { x0, y0, x1, y1 } = dragState;
  const color = getColor();
  if (editState.mode === "line") {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineCap = "round";
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.setLineDash([]);
    return;
  }
  const x = Math.min(x0, x1), y = Math.min(y0, y1);
  const w = Math.abs(x1 - x0), h = Math.abs(y1 - y0);
  if (editState.mode === "highlight") {
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.3;
    ctx.fillRect(x, y, w, h);
    ctx.globalAlpha = 1.0;
    return;
  }
  if (editState.mode === "ellipse") {
    ctx.strokeStyle = color;
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    return;
  }
  // rect (and underline/strikeout/image — they all show the same dashed box)
  ctx.strokeStyle = color;
  ctx.setLineDash([5, 4]);
  ctx.lineWidth = 1.5;
  ctx.strokeRect(x, y, w, h);
  ctx.setLineDash([]);
}

function drawCurrentInk() {
  const overlay = document.getElementById("peOverlayCanvas");
  if (!overlay) return;
  const ctx = overlay.getContext("2d");
  redrawOverlay();
  ctx.strokeStyle = getColor();
  ctx.lineWidth = 1.5 * _bitmapPerPoint();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const stroke of inkStrokes) {
    ctx.beginPath();
    stroke.forEach(([x, y], i) => {
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
}

// =========================================================================
// 5. Operations + save
// =========================================================================
function pushOp(op) {
  const list = editState.opsByPage.get(editState.pageNo) || [];
  list.push(op);
  editState.opsByPage.set(editState.pageNo, list);
  refreshSaveButton();
  setStatus("Operasyon eklendi (toplam " + totalOpCount() + ").", "ok");
}

function totalOpCount() {
  let n = 0;
  for (const arr of editState.opsByPage.values()) n += arr.length;
  return n;
}

function refreshSaveButton() {
  const btn = document.getElementById("peSaveBtn");
  if (!btn) return;
  btn.disabled = totalOpCount() === 0;
}

function undoLast() {
  const list = editState.opsByPage.get(editState.pageNo) || [];
  if (!list.length) {
    setStatus("Bu sayfada geri alınacak işlem yok.", "err");
    return;
  }
  list.pop();
  editState.opsByPage.set(editState.pageNo, list);
  redrawOverlay();
  refreshSaveButton();
  setStatus("Son işlem geri alındı (" + totalOpCount() + " kaldı).", "ok");
}

function clearPage() {
  editState.opsByPage.delete(editState.pageNo);
  redrawOverlay();
  refreshSaveButton();
  setStatus("Bu sayfanın tüm işlemleri silindi.", "ok");
}

async function saveEdits() {
  if (!editState.file) return;
  const ops = [];
  for (const arr of editState.opsByPage.values()) ops.push(...arr);
  if (!ops.length) return;
  setStatus("Kaydediliyor…");
  try {
    const fd = new FormData();
    fd.append("file", editState.file);
    fd.append("operations", JSON.stringify(ops));
    const r = await fetch(SAVE_ENDPOINT, { method: "POST", body: fd });
    if (!r.ok) {
      let msg = "HTTP " + r.status;
      try {
        const j = await r.json();
        if (j && j.detail) msg = j.detail;
      } catch (e) { /* not JSON */ }
      throw new Error(msg);
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const baseName = (editState.file.name || "edited").replace(/\.pdf$/i, "");
    a.href = url;
    a.download = baseName + "_edited.pdf";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1500);
    const applied = r.headers.get("X-Operations-Applied") || "?";
    const skipped = r.headers.get("X-Operations-Skipped") || "0";
    setStatus("İndirildi · " + applied + " uygulandı, " + skipped + " atlandı.", "ok");
  } catch (err) {
    setStatus("Kaydetme başarısız: " + (err?.message || err), "err");
  }
}

// =========================================================================
// 6. Mode picker + UI helpers
// =========================================================================
function switchTopMode(btn) {
  if (btn.disabled) return;
  document.querySelectorAll(".pe-mode").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  const top = btn.dataset.mode || "view";

  // Show / hide the relevant submode grid + replace hint
  const annotGrid = document.getElementById("peSubmodes");
  const overlayGrid = document.getElementById("peOverlaySubmodes");
  const replaceHint = document.getElementById("peReplaceHint");
  const granRow = document.getElementById("peGranularityRow");
  if (annotGrid)   annotGrid.style.display   = (top === "annot")   ? "" : "none";
  if (overlayGrid) overlayGrid.style.display = (top === "overlay") ? "" : "none";
  if (replaceHint) replaceHint.style.display = (top === "replace") ? "" : "none";
  if (granRow)     granRow.style.display     = (top === "replace") ? "" : "none";

  if (top === "annot") {
    editState.mode = "highlight";
  } else if (top === "overlay") {
    editState.mode = "text";
  } else if (top === "replace") {
    editState.mode = "replace";
    ensureSpansLoaded();
  } else {
    editState.mode = top;
  }
  setActiveSubMode(editState.mode);
  setCursor();
  document.getElementById("peModeLabel").textContent = "Mod: " + (btn.textContent || "").trim();
  redrawOverlay();
}

async function ensureSpansLoaded(force = false) {
  if (!editState.file || editState.spansLoading) return;
  if (!force && editState.spans.length) return;
  editState.spansLoading = true;
  setStatus("Metin parçaları taranıyor…");
  try {
    const fd = new FormData();
    fd.append("file", editState.file);
    fd.append("granularity", editState.granularity);
    fd.append("merge_adjacent", "true");
    fd.append("max_pages", "0");
    const r = await fetch(SPANS_ENDPOINT, { method: "POST", body: fd });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    editState.spans = Array.isArray(data.spans) ? data.spans : [];
    editState.extractability = data.extractability || null;
    updatePdfTypeBadge();
    if (editState.extractability && !editState.extractability.extractable) {
      setStatus(editState.extractability.message || "Bu PDF metin değiştirmeye uygun değil.", "err");
    } else {
      setStatus(editState.spans.length + " metin parçası bulundu.", "ok");
    }
    redrawOverlay();
  } catch (err) {
    setStatus("Metin parçaları alınamadı: " + (err?.message || err), "err");
  } finally {
    editState.spansLoading = false;
  }
}

function updatePdfTypeBadge() {
  const badge = document.getElementById("pePdfTypeBadge");
  if (!badge) return;
  const ext = editState.extractability;
  if (!ext) {
    badge.style.display = "none";
    return;
  }
  const labels = {
    vector: { text: "Vektör (metin)", bg: "rgba(34,197,94,0.25)" },
    image:  { text: "Görsel/Taranmış", bg: "rgba(220,38,38,0.30)" },
    hybrid: { text: "Karışık", bg: "rgba(245,158,11,0.30)" },
    empty:  { text: "Boş", bg: "rgba(148,163,184,0.30)" },
  };
  const info = labels[ext.type] || { text: ext.type || "—", bg: "rgba(255,255,255,0.18)" };
  badge.textContent = info.text;
  badge.style.background = info.bg;
  badge.title = ext.message || "";
  badge.style.display = "";
}

function setActiveSubMode(name) {
  document.querySelectorAll(".pe-submode").forEach((b) => b.classList.toggle("active", b.dataset.submode === name));
}

function enableModes(yes) {
  document.querySelectorAll(".pe-mode").forEach((b) => {
    if (b.dataset.mode === "annot" || b.dataset.mode === "overlay" || b.dataset.mode === "replace") {
      b.disabled = !yes;
    }
  });
  document.querySelectorAll(".pe-submode").forEach((b) => { b.disabled = !yes; });
  document.getElementById("peUndoBtn").disabled = !yes;
  document.getElementById("peClearBtn").disabled = !yes;
  document.getElementById("peFontColor").disabled = !yes;
  document.getElementById("peFontFamily").disabled = !yes;
  document.getElementById("peFontSize").disabled = !yes;
  document.getElementById("peFontBold").disabled = !yes;
  document.getElementById("peFontItalic").disabled = !yes;
  if (yes) {
    refreshBoldItalicAvailability();
    // Default to highlight when a doc is loaded
    const ann = document.querySelector(".pe-mode[data-mode='annot']");
    if (ann) ann.click();
  }
}

function setNavEnabled(yes) {
  ["pePrevBtn", "peNextBtn", "peZoomInBtn", "peZoomOutBtn"].forEach((id) => {
    const e = document.getElementById(id);
    if (e) e.disabled = !yes;
  });
}

function setStatus(msg, kind) {
  const s = document.getElementById("peStatus");
  if (!s) return;
  s.textContent = msg;
  s.className = "pe-status" + (kind ? " " + kind : "");
}

function _t(s) {
  return (window.HTI18N && typeof HTI18N.t === "function") ? HTI18N.t(s) : s;
}

// =========================================================================
// 7. Image picker (for "image" mode)
// =========================================================================
function pendingImageDataUrl() {
  editState.pendingImageDataUrl = null;
  const lbl = document.getElementById("peImageStatus");
  if (lbl) lbl.textContent = "";
}

function pickImageThen(cb) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/png,image/jpeg,image/webp";
  input.style.display = "none";
  input.addEventListener("change", () => {
    const f = input.files && input.files[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      editState.pendingImageDataUrl = reader.result;
      const lbl = document.getElementById("peImageStatus");
      if (lbl) lbl.textContent = f.name;
      setStatus("Görsel hazır — yerleştirmek için canvas'a sürükleyin.", "ok");
      if (cb) cb();
    };
    reader.readAsDataURL(f);
  });
  document.body.appendChild(input);
  input.click();
  setTimeout(() => input.remove(), 5000);
}

// Expose image picker to a sidebar button
window.__peSelectImage = () => pickImageThen();

// =========================================================================
// 9. Inline text editor (overlay "text" mode)
// =========================================================================
function cssFamilyForId(id) {
  const map = {
    "noto-sans":   "'Noto Sans', Arial, sans-serif",
    "noto-serif":  "'Noto Serif', 'Times New Roman', serif",
    "noto-mono":   "'Noto Sans Mono', Consolas, monospace",
    "dejavu-sans": "'DejaVu Sans', Arial, sans-serif",
    "dejavu-serif":"'DejaVu Serif', 'Times New Roman', serif",
    "dejavu-mono": "'DejaVu Sans Mono', Consolas, monospace",
  };
  return map[id] || "Arial, sans-serif";
}

function getFontId() {
  return document.getElementById("peFontFamily")?.value || "noto-sans";
}
function getFontSize() {
  const v = parseFloat(document.getElementById("peFontSize")?.value || "12");
  return Math.max(4, Math.min(200, v));
}
function getBold()   { return !!document.getElementById("peFontBold")?.checked; }
function getItalic() { return !!document.getElementById("peFontItalic")?.checked; }

function spawnTextEditor(canvasX, canvasY) {
  const stack = document.getElementById("peStack");
  if (!stack) return;
  const overlay = document.getElementById("peOverlayCanvas");
  // Convert canvas pixel coords back to overlay-style px coords (responsive)
  const rect = overlay.getBoundingClientRect();
  const scaleX = rect.width / overlay.width;
  const scaleY = rect.height / overlay.height;
  const cssX = canvasX * scaleX;
  const cssY = canvasY * scaleY;

  // Textarea font size lives in CSS pixels, not bitmap. Don't multiply by
  // scaleY (which already accounts for the dpr-scaled bitmap).
  const fontPx = getFontSize() * editState.scale;
  const ta = document.createElement("textarea");
  ta.className = "pe-text-editor";
  ta.placeholder = _t("Metin yazın · Enter ile onayla, Esc ile iptal");
  ta.style.position = "absolute";
  ta.style.left = cssX + "px";
  ta.style.top = cssY + "px";
  ta.style.minWidth = "120px";
  ta.style.minHeight = (fontPx * 1.4) + "px";
  ta.style.padding = "2px 4px";
  ta.style.border = "1px dashed #2F5496";
  ta.style.outline = "0";
  ta.style.background = "rgba(255,255,255,0.95)";
  ta.style.fontFamily = cssFamilyForId(getFontId());
  ta.style.fontSize = fontPx + "px";
  ta.style.fontWeight = getBold() ? "bold" : "normal";
  ta.style.fontStyle = getItalic() ? "italic" : "normal";
  ta.style.color = getColor();
  ta.style.lineHeight = "1.15";
  ta.style.zIndex = "5";
  ta.style.resize = "both";
  ta.rows = 1;
  stack.appendChild(ta);
  ta.focus();

  const commit = () => {
    const value = ta.value;
    ta.remove();
    if (!value.trim()) return;
    pushOp({
      type: "text",
      page: editState.pageNo,
      point: canvasToPdfPair(canvasX, canvasY),
      text: value,
      font_id: getFontId(),
      fontsize: getFontSize(),
      color: hexToRgb(getColor()),
      bold: getBold(),
      italic: getItalic(),
    });
    redrawOverlay();
  };
  const cancel = () => { ta.remove(); };

  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      commit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancel();
    }
  });
  ta.addEventListener("blur", () => {
    // Small delay so clicks on toolbar don't double-fire commit
    setTimeout(commit, 100);
  });
}

function spawnReplaceEditor(span) {
  const stack = document.getElementById("peStack");
  const overlay = document.getElementById("peOverlayCanvas");
  if (!stack || !overlay) return;
  const [cx0, cy0, cx1, cy1] = pdfRectToCanvas(span.rect);
  const overlayRect = overlay.getBoundingClientRect();
  const sx = overlayRect.width / overlay.width;
  const sy = overlayRect.height / overlay.height;

  const ta = document.createElement("textarea");
  ta.className = "pe-text-editor";
  ta.value = span.text;
  ta.placeholder = _t("Yeni metin · boş bırakılırsa silinir");
  ta.style.position = "absolute";
  ta.style.left = (cx0 * sx) + "px";
  ta.style.top = (cy0 * sy) + "px";
  ta.style.width = Math.max(80, (cx1 - cx0) * sx + 60) + "px";
  ta.style.minHeight = ((cy1 - cy0) * sy + 6) + "px";
  ta.style.padding = "1px 3px";
  ta.style.border = "2px solid #dc2626";
  ta.style.outline = "0";
  ta.style.background = "rgba(254, 242, 242, 0.95)";
  ta.style.fontFamily = cssFamilyForId(span.font_id);
  ta.style.fontSize = (span.fontsize * editState.scale) + "px";
  ta.style.fontWeight = span.bold ? "bold" : "normal";
  ta.style.fontStyle = span.italic ? "italic" : "normal";
  ta.style.color = rgbToCss(span.color);
  ta.style.lineHeight = "1.15";
  ta.style.zIndex = "5";
  ta.style.resize = "both";
  stack.appendChild(ta);
  ta.focus();
  ta.select();

  const commit = () => {
    const value = ta.value;
    ta.remove();
    pushOp({
      type: "replace",
      page: span.page,
      rect: span.rect.slice(),
      text: value,
      font_id: span.font_id,
      fontsize: span.fontsize,
      color: span.color.slice(),
      bold: span.bold,
      italic: span.italic,
      original_text: span.text,
    });
    redrawOverlay();
  };
  const cancel = () => { ta.remove(); };

  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      commit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancel();
    }
  });
  ta.addEventListener("blur", () => setTimeout(commit, 100));
}

// =========================================================================
// 8. Boot
// =========================================================================
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootEditor);
} else {
  bootEditor();
}
