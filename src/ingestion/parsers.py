"""Turn 911records.org HTML pages into Python dicts (no downloading here).

The site has no public API, so these parsers work from the rendered HTML.
They are written defensively (several strategies per field) because the
markup can change. ALWAYS run `python main.py inspect <url>` on a few
pages first and check that the printed fields look right; if something is
empty, open the saved HTML and adjust the label lists / selectors below.
Raw HTML is cached, so after a fix, re-running a step costs no new requests.
"""
from __future__ import annotations

import json
import re
from typing import Iterable

from bs4 import BeautifulSoup, Tag

DOC_ID_RE = re.compile(r"NYC-WTC_\d{9}")
DOC_PAGE_HREF_RE = re.compile(r"/doc/(NYC-WTC_\d{9})(?:/p/(\d+))?")
ENTITY_HREF_RE = re.compile(r"/entity/([a-z_-]+)/([^/?#]+)")
BUILDING_HREF_RE = re.compile(r"/building/(\d+)")
NUM = r"(\d[\d,]*)"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _int(s: str | None) -> int | None:
    if s is None:
        return None
    s = s.replace(",", "").strip()
    return int(s) if s.isdigit() else None


def _clean(s: str | None) -> str | None:
    if s is None:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _lines(soup: BeautifulSoup) -> list[str]:
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return [ln for ln in (_clean(x) for x in soup.get_text("\n").split("\n")) if ln]


def _meta(soup: BeautifulSoup, key: str) -> str | None:
    tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    return tag.get("content") if tag else None


def labeled_values(soup: BeautifulSoup) -> dict[str, str]:
    """Collect label -> value pairs using several common markup patterns.

    Keys are lower-cased labels with spaces around '/' removed
    (e.g. 'box/folder'). First occurrence wins.
    """
    out: dict[str, str] = {}

    def put(k: str, v: str) -> None:
        k = re.sub(r"\s*/\s*", "/", (k or "").strip().rstrip(":").lower())
        v = _clean(v)
        if k and v and k not in out and len(k) < 40:
            out[k] = v

    for dt in soup.find_all("dt"):  # <dl><dt>label</dt><dd>value</dd>
        dd = dt.find_next_sibling("dd")
        if dd:
            put(dt.get_text(" "), dd.get_text(" "))
    for tr in soup.find_all("tr"):  # <tr><th>label</th><td>value</td>
        cells = tr.find_all(["th", "td"])
        if len(cells) == 2:
            put(cells[0].get_text(" "), cells[1].get_text(" "))
    # "Label: value" inside one element, or label element followed by sibling
    for el in soup.find_all(["span", "div", "p", "li", "strong", "b", "h4", "h5", "label"]):
        txt = _clean(el.get_text(" ")) or ""
        if len(txt) > 200:
            continue
        m = re.match(r"^([A-Za-z][A-Za-z /&-]{1,35}):\s+(.+)$", txt)
        if m:
            put(m.group(1), m.group(2))
        elif len(txt) <= 35 and not el.find(["div", "p", "li"]):
            sib = el.find_next_sibling()
            if isinstance(sib, Tag):
                stxt = _clean(sib.get_text(" "))
                if stxt and len(stxt) < 300:
                    put(txt, stxt)
    return out


def _pick(vals: dict[str, str], *labels: str) -> str | None:
    for lab in labels:
        lab = re.sub(r"\s*/\s*", "/", lab.lower())
        if lab in vals:
            return vals[lab]
    return None


def _json_blobs(soup: BeautifulSoup) -> list[dict]:
    """JSON-LD / __NEXT_DATA__ blobs, if the site embeds any."""
    blobs = []
    for s in soup.find_all("script"):
        if s.get("type") in ("application/ld+json", "application/json") or s.get("id") == "__NEXT_DATA__":
            try:
                blobs.append(json.loads(s.string or ""))
            except (json.JSONDecodeError, TypeError):
                pass
    return blobs


_CONF_RE = re.compile(r"confidence\s*(\d+(?:\.\d+)?)\s*(%?)", re.I)


def _split_conf(v: str | None) -> tuple[str | None, float | None]:
    if not v:
        return None, None
    m = _CONF_RE.search(v)
    conf = None
    if m:
        conf = float(m.group(1)) / (100 if m.group(2) == "%" else 1)
        v = _clean(_CONF_RE.sub("", v).strip(" ·,-"))
    return v, conf


# --------------------------------------------------------------------- doc page
def parse_doc_page(html: str, url: str = "") -> dict:
    """Parse /doc/{id} or /doc/{id}/p/{n}: city metadata, machine fields, OCR text."""
    soup = _soup(html)
    og_title = _meta(soup, "og:title")
    desc_meta = _meta(soup, "og:description") or _meta(soup, "description")
    page_m = re.search(r"/p/(\d+)", url)
    m_id = DOC_ID_RE.search(url) or DOC_ID_RE.search(og_title or "")
    doc_id = m_id.group(0) if m_id else None

    # ---- OCR text: heading "OCR text" -> next <pre> or fallback container, else longest <pre>
    ocr = None
    head = soup.find(lambda t: t.name in ("h1", "h2", "h3", "h4", "summary") and "ocr text" in t.get_text(" ").lower())
    if head:
        pre = head.find_next("pre")
        if pre:
            ocr = pre.get_text("\n")
        else:
            container = head.find_next(["div", "p", "code"])
            if container:
                next_el = (
                    container.find_next_sibling(["pre", "div", "p"])
                    if "ocr status:" in container.get_text().lower()
                    else container
                )
                if next_el:
                    ocr = next_el.get_text("\n").strip()
    if ocr is None:
        pres = soup.find_all("pre")
        if pres:
            ocr = max((p.get_text("\n") for p in pres), key=len)

    links_entities = sorted({
        (m.group(1), m.group(2))
        for a in soup.find_all("a", href=True)
        if (m := ENTITY_HREF_RE.search(a["href"]))
    })
    links_buildings = sorted({
        m.group(1)
        for a in soup.find_all("a", href=True)
        if (m := BUILDING_HREF_RE.search(a["href"]))
    })
    pdf_links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].lower().endswith(".pdf")]

    vals = labeled_values(soup)
    text_lines = _lines(_soup(html))
    full = "\n".join(text_lines)

    # ---- Title confidence (supports comma or middle dot '·' separator)
    title_conf = None
    if (m := re.search(r"machine-extracted title[,\s·]+confidence\s*(\d+)%", full, re.I)):
        title_conf = int(m.group(1)) / 100

    # ---- Description (labeled value, paragraph below <h1>, or meta description fallback)
    description = _pick(vals, "description")
    if not description:
        h1 = soup.find("h1")
        if h1:
            for sib in h1.find_next_siblings(["p", "div"], limit=3):
                stxt = _clean(sib.get_text(" "))
                if stxt and "machine-extracted title" not in stxt.lower() and not stxt.startswith("NYC-WTC_"):
                    description = stxt
                    break
    if not description and desc_meta:
        description = desc_meta

    # ---- Document type & confidence
    doc_type, doc_type_conf = _split_conf(_pick(vals, "document type", "type"))
    if doc_type is None:
        m_dt = re.search(r"^(.+?)\s+Machine-extracted document type\s*·\s*confidence\s*(\d+)%", full, re.M | re.I)
        if m_dt:
            doc_type = _clean(m_dt.group(1))
            doc_type_conf = int(m_dt.group(2)) / 100

    # ---- Contaminants
    contaminants_raw = _pick(vals, "contaminant(s)", "contaminants", "substance", "substances")
    contaminants = [c.strip() for c in contaminants_raw.split(",") if c.strip()] if contaminants_raw else []

    ocr_status = re.search(r"OCR status:\s*([\w-]+)\s*·?\s*source:\s*([\w.-]+)", full, re.I)
    page_of = re.search(r"Page\s+(\d+)\s+of\s+(\d+)", full)
    pages_size = _pick(vals, "pages/file size", "pages", "document length")
    n_pages = _int(page_of.group(2)) if page_of else None
    if n_pages is None and pages_size and (m := re.search(NUM + r"\s*pages?", pages_size)):
        n_pages = _int(m.group(1))
    box_folder = _pick(vals, "box/folder", "box")

    return {
        "doc_id": doc_id,
        "page": int(page_m.group(1)) if page_m else 1,
        "url": url,
        "title": (og_title or "").split(" · ")[0] or None,
        "title_confidence": title_conf,
        "description": description,
        "collection": _pick(vals, "collection"),
        "agency": _pick(vals, "agency"),
        "box_folder": box_folder,
        "box": box_folder.split("/")[0].strip() if box_folder else None,
        "folder": box_folder.split("/", 1)[1].strip().strip('"') if box_folder and "/" in box_folder else None,
        "folder_label": _pick(vals, "folder label"),
        "production_volume": _pick(vals, "production volume"),
        "bates_range": _pick(vals, "bates range") or (desc_meta or "").split(",")[0].replace("Bates ", "") or None,
        "n_pages": n_pages,
        "file_size": pages_size,
        "doc_type": doc_type,
        "doc_type_confidence": doc_type_conf,
        "doc_date_raw": _pick(vals, "date", "dates", "date(s)"),
        "contaminants": contaminants,
        "ocr_status": ocr_status.group(1) if ocr_status else None,
        "ocr_source": ocr_status.group(2) if ocr_status else None,
        "ocr_text": ocr,
        "entity_links": json.dumps(links_entities),
        "building_bins": json.dumps(links_buildings),
        "pdf_links": json.dumps(pdf_links),
        "has_json_blob": bool(_json_blobs(soup)),
    }



# ---------------------------------------------------------- entity listings
SIGNATORY_HREF_RE = re.compile(r"^/signatory/([^/?#]+)")

def parse_entity_listing(html: str, etype: str) -> tuple[list[dict], list[str]]:
    """Parse /entities/{etype}. Returns (rows, other listing URLs to visit)."""
    soup = _soup(html)
    rows, seen = [], set()

    for a in soup.find_all("a", href=True):
        m = ENTITY_HREF_RE.search(a["href"])
        b = BUILDING_HREF_RE.search(a["href"])
        s = SIGNATORY_HREF_RE.search(a["href"]) if etype == "signatory" else None

        if not (m and m.group(1) == etype) and not (b and etype == "address") and not s:
            continue

        key = a["href"].split("#")[0]
        if key in seen:
            continue
        seen.add(key)

        row_el = a.find_parent(["li", "tr", "article"]) or a.parent
        row_txt = _clean(row_el.get_text(" ")) if row_el else ""
        pages = re.search(NUM + r"\s*(?:source\s+)?pages?", row_txt or "", re.I)
        docs = re.search(NUM + r"\s*doc(?:ument)?s?", row_txt or "", re.I)
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", row_txt or "")

        if m:
            ent_type, slug = etype, m.group(2)
        elif b:
            ent_type, slug = "building", b.group(1)
        else:
            ent_type, slug = "signatory", s.group(1)

        rows.append({
            "entity_type": ent_type,
            "slug": slug,
            "name": _clean(a.get_text(" ")),
            "href": key,
            "n_pages": _int(pages.group(1)) if pages else None,
            "n_docs": _int(docs.group(1)) if docs else None,
            "first_date": min(dates) if dates else None,
            "last_date": max(dates) if dates else None,
            "row_text": row_txt,
        })

    nxt = sorted({
        a["href"] for a in soup.find_all("a", href=True)
        if re.match(rf"^(https://911records\.org)?/entities/{etype}\?", a["href"])
    })
    return rows, nxt


# ------------------------------------------------------------- entity detail
def parse_entity_page(html: str, etype: str, slug: str) -> dict:
    """Parse /entity/{etype}/{slug}[?page=N]: (doc, page) links + related entities."""
    soup = _soup(html)
    scope = soup.find(id="records") or soup  # restrict to records section if present
    links = []
    for a in scope.find_all("a", href=True):
        m = DOC_PAGE_HREF_RE.search(a["href"])
        if m and m.group(2):
            row_el = a.find_parent(["li", "tr", "article"]) or a.parent
            row_txt = _clean(row_el.get_text(" ")) if row_el else None
            conf = _CONF_RE.search(row_txt or "")
            links.append({
                "entity_type": etype, "slug": slug, "doc_id": m.group(1), "page": int(m.group(2)),
                "link_text": _clean(a.get_text(" ")),
                "confidence": float(conf.group(1)) / (100 if conf.group(2) == "%" else 1) if conf else None,
                "row_text": row_txt,
            })
    related = []
    rel_scope = soup.find(id=re.compile("related", re.I)) or soup
    for a in rel_scope.find_all("a", href=True):
        m = ENTITY_HREF_RE.search(a["href"])
        if not m or (m.group(1) == etype and m.group(2) == slug):
            continue
        row_el = a.find_parent(["li", "tr"]) or a.parent
        row_txt = _clean(row_el.get_text(" ")) or ""
        n = re.search(NUM + r"\s*shared", row_txt) or re.search(NUM + r"\s*pages?", row_txt)
        related.append({
            "src_type": etype, "src_slug": slug,
            "dst_type": m.group(1), "dst_slug": m.group(2), "dst_name": _clean(a.get_text(" ")),
            "shared_pages": _int(n.group(1)) if n else None,
        })
    full = "\n".join(_lines(_soup(html)))
    tot = re.search(r"Showing\s+[\d,]+\s*[–-]\s*[\d,]+\s+of\s+" + NUM, full, re.I)
    name = soup.find("h1")
    return {
        "name": _clean(name.get_text(" ")) if name else slug,
        "links": links,
        "related": related,
        "total_records": _int(tot.group(1)) if tot else None,
    }


# ------------------------------------------------------------- building page
def parse_building_page(html: str, bin_: str) -> dict:
    soup = _soup(html)
    vals = labeled_values(soup)
    h1 = soup.find("h1")
    links = []
    for a in soup.find_all("a", href=True):
        m = DOC_PAGE_HREF_RE.search(a["href"])
        if m and m.group(2):
            row_el = a.find_parent(["li", "tr", "article"]) or a.parent
            links.append({"bin": bin_, "doc_id": m.group(1), "page": int(m.group(2)),
                          "row_text": _clean(row_el.get_text(" ")) if row_el else None})
    full = "\n".join(_lines(_soup(html)))
    summary = re.search(NUM + r"\s*records?.{0,40}?" + NUM + r"\s*source pages?.{0,40}?" + NUM + r"\s*test candidate",
                        full, re.I | re.S)
    return {
        "bin": bin_,
        "name": _clean(h1.get_text(" ")) if h1 else None,
        "address": _pick(vals, "address"),
        "building_class": _pick(vals, "building class", "class"),
        "year_built": _int(re.sub(r"\D", "", _pick(vals, "year built") or "") or None),
        "floors": _int(re.sub(r"\D", "", _pick(vals, "floors") or "") or None),
        "units": _pick(vals, "units"),
        "building_area": _pick(vals, "building area"),
        "n_records": _int(summary.group(1)) if summary else None,
        "n_source_pages": _int(summary.group(2)) if summary else None,
        "n_test_candidate_pages": _int(summary.group(3)) if summary else None,
        "links": links,
    }


import json
from bs4 import BeautifulSoup

def parse_map_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    places = []

    for script in soup.find_all("script"):
        text = script.string or ""
        if "initialPlaces" not in text:
            continue
        unescaped = text.replace('\\"', '"').replace('\\\\', '\\')
        idx = unescaped.find('"initialPlaces":')
        if idx != -1:
            start = unescaped.find("[", idx)
            decoder = json.JSONDecoder()
            try:
                places, _ = decoder.raw_decode(unescaped, start)
                break
            except json.JSONDecodeError:
                continue

    buildings = []
    for p in places:
        n_test = p.get("n_test_pages", 0) or 0
        n_insp = p.get("n_inspection_pages", 0) or 0

        if n_test > 0:
            record_type = "test"
        elif n_insp > 0:
            record_type = "inspection"
        else:
            record_type = "mentioned"

        bin_id = p.get("key") if p.get("kind") == "bin" else p.get("id")

        buildings.append({
            "bin": str(bin_id),
            "place_id": p.get("id"),
            "kind": p.get("kind"),
            "address": p.get("label"),
            "lat": p.get("lat"),
            "lon": p.get("lon"),
            "n_docs": p.get("n_docs"),
            "n_pages": p.get("n_pages"),
            "n_test_pages": n_test,
            "n_inspection_pages": n_insp,
            "record_type": record_type,
            "first_date": p.get("first_date"),
            "last_date": p.get("last_date"),
        })

    return buildings



def doc_ids_in(html: str) -> Iterable[str]:
    return sorted(set(DOC_ID_RE.findall(html)))


# ------------------------------------------------------------------ browse
BROWSE_HREF_RE = re.compile(r"^(?:https://911records\.org)?(/browse(?:/[^#]*)?)$")


def parse_browse(html: str) -> tuple[list[dict], list[str]]:
    """Doc rows and further /browse links (boxes, pagination) on a browse page."""
    soup = _soup(html)
    docs, nav, seen = [], set(), set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0]
        m = DOC_PAGE_HREF_RE.search(href)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            row = a.find_parent(["li", "tr", "article"]) or a.parent
            docs.append({"doc_id": m.group(1), "row_text": _clean(row.get_text(" ")) if row else None})
        elif (b := BROWSE_HREF_RE.match(href)):
            nav.add(b.group(1))
    return docs, sorted(nav)


# ----------------------------------------------------------------- changes
CHANGES_HREF_RE = re.compile(r"/changes/(\d{4}-\d{2}-\d{2})")


def _num_near(txt: str, word: str) -> int | None:
    m = re.search(NUM + r"\s*(?:documents?\s+)?" + word, txt, re.I) or re.search(word + r"\s*:?\s*\+?" + NUM, txt, re.I)
    return _int(m.group(1)) if m else None


def parse_changes_index(html: str) -> tuple[list[dict], list[str]]:
    """Capture rows (totals and counts) and links to per-capture pages."""
    soup = _soup(html)
    links = sorted({m.group(1) for a in soup.find_all("a", href=True) if (m := CHANGES_HREF_RE.search(a["href"]))})
    rows, seen = [], set()
    for el in soup.find_all(["li", "tr", "article", "section"]):
        txt = _clean(el.get_text(" ")) or ""
        a = el.find("a", href=CHANGES_HREF_RE)
        if not a or len(txt) > 600:
            continue
        d = CHANGES_HREF_RE.search(a["href"]).group(1)
        if d in seen:
            continue
        seen.add(d)
        gb = re.search(r"(\d+(?:\.\d+)?)\s*GB", txt)
        rows.append({"capture_date": d, "documents": _num_near(txt, "documents"), "pages": _num_near(txt, "pages"),
                     "size_gb": float(gb.group(1)) if gb else None, "added": _num_near(txt, "added"),
                     "removed": _num_near(txt, "removed"), "changed": _num_near(txt, "changed"), "raw": txt})
    return rows, links


def parse_change_capture(html: str, capture_date: str) -> list[dict]:
    """(change, doc_id) rows; the change type comes from the nearest preceding heading."""
    from bs4 import NavigableString

    soup = _soup(html)
    main = soup.find("main") or soup
    state, rows, seen = None, [], set()
    for node in main.descendants:
        if isinstance(node, Tag) and node.name in ("h1", "h2", "h3", "h4", "summary", "dt", "caption"):
            low = node.get_text(" ").lower()
            for k in ("removed", "added", "changed"):
                if k in low:
                    state = k
                    break
        ids: list[str] = []
        if isinstance(node, Tag) and node.name == "a" and node.get("href"):
            ids = DOC_ID_RE.findall(node["href"])
        elif isinstance(node, NavigableString) and node.parent.name != "a":
            ids = DOC_ID_RE.findall(str(node))
        for d in ids:
            if state and (state, d) not in seen:
                seen.add((state, d))
                ctx = node.parent if isinstance(node, NavigableString) else node.find_parent(["li", "tr"]) or node
                rows.append({"capture_date": capture_date, "change": state, "doc_id": d,
                             "context": _clean(ctx.get_text(" "))[:300] if ctx else None})
    return rows


# ---------------------------------------------------------- contradictions
def parse_contradictions(html: str) -> list[dict]:
    """One row per (entry, cited doc page). Entries are split on h2/h3 headings."""
    soup = _soup(html)
    main = soup.find("main") or soup
    heads = main.find_all(["h2", "h3"])
    rows, entry = [], 0
    for h in heads:
        level = int(h.name[1])
        texts, links = [], []
        for el in h.next_elements:
            if isinstance(el, Tag) and el.name in ("h2", "h3") and int(el.name[1]) <= level and el is not h:
                break
            if isinstance(el, Tag) and el.name == "a" and el.get("href"):
                m = DOC_PAGE_HREF_RE.search(el["href"])
                if m:
                    links.append((m.group(1), int(m.group(2) or 1), _clean(el.get_text(" "))))
            elif not isinstance(el, Tag):
                t = str(el).strip()
                if t:
                    texts.append(t)
        if not links:
            continue
        entry += 1
        body = _clean(" ".join(texts))
        for d, p, lt in dict.fromkeys(links):
            rows.append({"entry_id": entry, "heading": _clean(h.get_text(" ")), "doc_id": d, "page": p,
                         "link_text": lt, "entry_text": body})
    return rows
