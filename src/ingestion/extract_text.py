"""Get the text of every page from the PDFs.

For each page:
  1. pdftotext reads the text already embedded in the PDF. This is the same
     text 911records.org shows ("source: pdftotext"), with no web requests.
  2. If the page has no text (a scanned image), OCR it with Tesseract.
  3. If it's still empty, fetch that one page's text from the site.

Gets data/interim/pages.jsonl: doc_id, page, text, source (pdftotext /
tesseract / site / none), ocr_confidence.

Needs: poppler (pdftotext, pdftoppm, pdfinfo) and tesseract installed.
Run alone:  python -m src.ingestion.extract_text
Resumable: finished documents are in text_done.txt.
"""
import multiprocessing as mp
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import config
from src.ingestion.files import append_rows, done_keys, mark_done


def pdftotext_pages(pdf):
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, timeout=900)
    pages = out.stdout.decode("utf-8", "replace").split("\f")      # \f separates pages
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    n = next((int(l.split()[1]) for l in info.splitlines() if l.startswith("Pages:")), len(pages) - 1)
    return (pages + [""] * n)[:n]


def tesseract_page(pdf, page):
    """OCR one page. Returns (text, mean word confidence 0-100)."""
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "page"
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "300", "-gray", "-png",
                        "-singlefile", str(pdf), str(img)], check=True, capture_output=True)
        tsv = subprocess.run(["tesseract", f"{img}.png", "stdout", "tsv"], capture_output=True, text=True).stdout
    lines, confs = {}, []
    for row in tsv.splitlines()[1:]:
        f = row.split("\t")
        if len(f) == 12 and f[0] == "5" and f[11].strip():          # level 5 = word
            lines.setdefault((int(f[2]), int(f[3]), int(f[4])), []).append(f[11])
            confs.append(float(f[10]))
    text = "\n".join(" ".join(words) for _, words in sorted(lines.items()))
    return text, (sum(confs) / len(confs) if confs else None)


def process_pdf(doc_id, pdf):
    """Runs in a worker process: all pages of one document."""
    rows = []
    for i, text in enumerate(pdftotext_pages(pdf), 1):
        source, conf = "pdftotext", None
        if len(text.strip()) < config.MIN_CHARS:
            source = "none"
            if config.USE_TESSERACT:
                try:
                    ocr_text, conf = tesseract_page(pdf, i)
                    if len(ocr_text.strip()) >= config.MIN_CHARS:
                        text, source = ocr_text, "tesseract"
                except Exception:
                    pass
        rows.append({"doc_id": doc_id, "page": i, "text": text, "source": source, "ocr_confidence": conf})
    return doc_id, rows


def site_fallback(rows):
    """For pages still empty, use the site's text for that page (one request each)."""
    from src.ingestion.parsers import parse_doc_page
    from src.ingestion.web import get_page

    for r in rows:
        if r["source"] == "none":
            url = f"{config.SITE}/doc/{r['doc_id']}" + (f"/p/{r['page']}" if r["page"] > 1 else "")
            html = get_page(url)
            text = parse_doc_page(html, url)["ocr_text"] if html else None
            if text and len(text.strip()) >= config.MIN_CHARS:
                r["text"], r["source"] = text, "site"
    return rows


def run():
    print("Extract page text")
    done = done_keys(config.INTERIM / "text_done.txt")
    pdfs = {p.stem: p for p in config.PDFS.rglob("*.pdf") if p.stem not in done}
    print(f"  {len(pdfs)} PDFs to process ({len(done)} done)")
    with ProcessPoolExecutor(config.TEXT_WORKERS, mp_context=mp.get_context("spawn")) as pool:
        jobs = [pool.submit(process_pdf, d, p) for d, p in pdfs.items()]
        for i, job in enumerate(as_completed(jobs), 1):
            try:
                doc_id, rows = job.result()
            except Exception as e:
                print(f"  failed: {e}")
                continue
            if config.USE_SITE_FALLBACK:
                rows = site_fallback(rows)
            append_rows(config.INTERIM / "pages.jsonl", rows)
            mark_done(config.INTERIM / "text_done.txt", [doc_id])
            if i % 100 == 0:
                print(f"  {i}/{len(pdfs)}")


if __name__ == "__main__":
    run()
