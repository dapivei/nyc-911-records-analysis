"""Get one PDF per document into data/raw/pdfs/.

Two ways, use either or both:
  a) Fastest: download ZIPs from https://911records.org/downloads in your
     browser (it asks for a quick human check), put them in data/raw/zips/.
     This step unzips them.
  b) Any PDF still missing is downloaded from the official City portal.

Run alone:  python -m src.ingestion.get_pdfs             (ZIPs + download)
            python -m src.ingestion.get_pdfs zips-only   (ZIPs only)
Resumable: PDFs already on disk are skipped.
"""
import shutil
import sys
import zipfile

import config
from src.ingestion.parsers import DOC_ID_RE
from src.ingestion.files import read_table


def pdf_path(doc_id):
    return config.PDFS / doc_id[8:14] / f"{doc_id}.pdf"   # sub-folders of ~1,000 files


def unzip_all():
    n = 0
    for z in sorted(config.ZIPS.glob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            for member in zf.infolist():
                m = DOC_ID_RE.search(member.filename)
                if not (m and member.filename.lower().endswith(".pdf")):
                    continue
                dest = pdf_path(m.group(0))       # never trust paths inside a ZIP
                if dest.exists():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
                n += 1
        print(f"  {z.name}: done ({n} new PDFs so far)")


def download_missing():
    from src.ingestion.scrape_docs import all_doc_ids
    from src.ingestion.web import download

    # if you only scraped a sample in step 2, only get PDFs for that sample
    docs = read_table(config.INTERIM / "docs.jsonl", ["doc_id"])
    ids = sorted(set(docs.doc_id)) if len(docs) else all_doc_ids()
    missing = [d for d in ids if not pdf_path(d).exists()]
    print(f"  {len(missing)} PDFs to download from the City portal")
    for i, doc_id in enumerate(missing, 1):
        if not download(config.CITY_PDF_URL.format(doc_id=doc_id), pdf_path(doc_id)):
            print(f"  could not get {doc_id}")
        if i % 100 == 0:
            print(f"  {i}/{len(missing)}")


def run(zips_only=False):
    print("Get PDFs")
    unzip_all()
    if not zips_only:
        download_missing()
    print(f"  PDFs on disk: {sum(1 for _ in config.PDFS.rglob('*.pdf'))}")


if __name__ == "__main__":
    run(zips_only="zips-only" in sys.argv)
