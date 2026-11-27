"""Reviewable organization classification for the RQ1 network.

Three hand-maintained inputs, each with a stated basis:

  COMPANY_MERGES     OCR / prefix variants of the same company that clean.py left apart
                     (e.g. "Landlord Silverstein Properties" -> silverstein-properties)
  ARTIFACT_IDS       extracted "company" names that are job titles or phrases, not organizations
  MANUAL_GROUPS      group assignments that keyword rules cannot make reliably

and two rules:

  is_generic_name()  a company name with no distinctive word ("Final Laboratory",
                     "Services Inc.") is an extraction artifact, not an organization
  keyword_group()    conservative keyword rules; anything else stays "other_unknown"

Groups were fixed before any centrality was computed. They are NOT tuned to the results.
Public-health advocacy groups do not occur among extracted entities at all (checked in
the notebook); they are only added in the exploratory text-dictionary supplement
(ADVOCACY_PATTERNS, see build.py).
"""
import re

import pandas as pd

# --- groups --------------------------------------------------------------------------
GROUP_LABELS = {
    "municipal_regulatory": "Municipal regulatory agency",
    "city_other": "Other NYC agency / city body",
    "state_federal_regional": "State, federal or bi-state agency",
    "private_real_estate": "Private real estate (owner, developer, manager)",
    "consultant_contractor_lab": "Environmental consultant, contractor or lab",
    "private_utility": "Private utility",
    "nonprofit_relief": "Relief nonprofit",
    "public_health_advocacy": "Public health / environmental advocacy group",
    "other_unknown": "Other / unknown",
}

# Municipal *regulatory* agencies: city bodies that issue or enforce environmental,
# health, building or housing rules. Fixed a priori. Other city agencies (OEM, Mayor,
# Law, DCAS, DDC, FDNY, NYPD, DSNY, Board of Education, DORIS) are operational or
# administrative and go to city_other; the broad variant (all city agencies) is a
# robustness check.
MUNICIPAL_REGULATORY = {
    "nyc-dep": "DEP: enforces asbestos/air rules (Title 15 RCNY), issued WTC cleanup guidance",
    "nyc-dohmh": "DOHMH: public-health regulator (Health Code), indoor-air guidance",
    "nyc-dob": "DOB: building code enforcement, permits",
    "nyc-hpd": "HPD: housing maintenance code enforcement",
}

# agency_level from src/processing/agency_map.py -> group (for the other agencies)
AGENCY_LEVEL_GROUP = {
    "city": "city_other", "state": "state_federal_regional", "federal": "state_federal_regional",
    "regional": "state_federal_regional", "private": "private_utility", "nonprofit": "nonprofit_relief",
}

# --- company merges (variant entity_id -> canonical entity_id) ------------------------
# Built from candidate pairs where one id is another id plus a 1-2 token prefix
# (notebook section 2). Only pairs checked by eye are listed; uncertain ones are not merged.
COMPANY_MERGES = {
    # Silverstein Properties: W. Weems / J. Ritorto are Silverstein staff names fused into the org name
    "landlord-silverstein-properties": "silverstein-properties",
    "w-weems-silverstein-properties": "silverstein-properties",
    "weems-silverstein-properties": "silverstein-properties",
    "joseph-ritorto-silverstein-properties": "silverstein-properties",
    "dcas-oem-silverstein-properties": "silverstein-properties",
    # RJ Lee Group: OCR spacing / leading fragment
    "rj-leegroup": "rj-lee-group",
    "if-rj-lee-group": "rj-lee-group",
    "ri-lee-group": "rj-lee-group",
    "rj-ijcegroup": "rj-lee-group",
    "lee-group": "rj-lee-group",
    # Warren & Panzer Engineers: OCR misspellings / "Name:" form field
    "wanen-and-panzer-engineers": "warren-and-panzer-engineers",
    "waiten-and-panzer-engineers": "warren-and-panzer-engineers",
    "name-warren-and-panzer-engineers": "warren-and-panzer-engineers",
    "namewarren-and-panzer-engineers": "warren-and-panzer-engineers",
    "panzer-engineers": "warren-and-panzer-engineers",          # truncated name
    # same lab, name with / without the service word
    "pace-analytical": "pace-analytical-services",
    "emsl-laboratory": "emsl-analytical",
    "testwell-laboratories": "testwell-laboratory",
    "if-aes": "aes",
    # GCI Environmental Advisory: OCR misspellings of the first token
    "gci-erivironmental-advisory": "gci-environmental-advisory",
    "gcl-environmental-advisory": "gci-environmental-advisory",
    "qci-environmental-advisory": "gci-environmental-advisory",
    # form-field prefixes ("Client:", "Name:", "Engineer:") fused into the name
    "engineer-cosentini-associates": "cosentini-associates",
    "client-ambient-group": "ambient-group",
    "name-ambient-group": "ambient-group",
    "name-trio-asbestos-removal": "trio-asbestos-removal",
    "clientphilip-analytical-services": "philip-analytical-services",
    "name-airtek-environmental": "airtek-environmental",
    "name-ets-contracting": "ets-contracting",
    "client-jack-resnick-and-sons": "jack-resnick-and-sons",
    "h-a-bader-consultants": "a-bader-consultants",
    "j-c-broderick-and-associates": "c-broderick-and-associates",
    # NYC Economic Development Corp.
    "nyc-economic-development": "new-york-city-economic-development",
}

# extracted "companies" that are not organizations (job titles, phrases, form labels)
ARTIFACT_IDS = {
    "agency-chief-contracting": "job title (Agency Chief Contracting Officer)",
    "environmental-protection-agency-chief-contracting": "job title (EPA / ACCO)",
    "acting-agency-chief-contracting": "job title",
    "deputy-agency-chief-contracting": "job title",
    "bureau-chief-contracting": "job title",
    "chief-contracting": "job title",
    "acting": "word 'Acting' + Corp.",
    "submit": "word 'Submit' + Co.",
    "world-trade": "phrase 'World Trade' (+ Co.)",
    "national-voluntary-laboratory": "NVLAP accreditation program name, not a lab",
    "nvlap-laboratory": "NVLAP accreditation program name, not a lab",
    "aiha-laboratory": "AIHA accreditation phrase",
    "elap-laboratory": "ELAP accreditation phrase",
    "nysdoh-elap-laboratory": "ELAP accreditation phrase",
    "ny-state-elap-laboratory": "ELAP accreditation phrase",
    "nysdoh-flap-laboratory": "ELAP accreditation phrase (OCR)",
    "flap-laboratory": "ELAP accreditation phrase (OCR)",
    "insurance": "generic word",
    "removal": "generic word",
    "engine": "generic word",
    "church": "generic word",
    "report": "word 'Report' + Co.",
    "send": "word 'Send' + Co.",
    "less-landlord-s-construction": "phrase from a lease clause",
}

# words that carry no identity on their own; a company name made only of these is generic
_GENERIC_WORDS = {
    # from src/processing/clean.py GENERIC_COMPANY_WORDS
    "associates", "construction", "development", "environmental", "engineering", "engineers",
    "services", "group", "consultants", "consulting", "contracting", "contractors", "management",
    "industries", "enterprises", "systems", "partners", "laboratories", "laboratory", "labs",
    "analytical", "testing", "international", "realty", "properties",
    # added for lab / OCR phrases seen in the entity table
    "inc", "llc", "llp", "lp", "pc", "pllc", "corp", "corporation", "co", "company", "ltd",
    "limited", "the", "and", "of", "for", "a", "an", "if", "to", "in", "by",
    "final", "deputy", "distribution", "accredited", "sample", "analysis", "commercial",
    "national", "voluntary", "new", "york", "ny", "nyc", "health", "scientific", "independent",
    "mobile", "interim", "transmission", "electron", "microscopy", "industrial", "hygiene",
    "air", "certified", "approved", "contract", "advisory", "real", "estate", "property",
    "owners", "holding", "holdings", "trust", "insurance", "air", "indoor", "outdoor",
    "pesticides", "organochlorine", "asbestos", "lead", "sampling", "methodology", "research",
    "technical", "technologies", "technology", "general", "client", "name", "engineer",
    "manager", "project", "contractor", "owner", "landlord", "agency", "chief", "office",
    "department", "bureau", "division", "city", "state", "federal", "economic", "public",
}
# a single surviving token this short is almost always an OCR fragment ("C Laboratory")
_MIN_DISTINCT_TOKEN_LEN = 2


def name_tokens(name: str) -> list[str]:
    name = str(name).lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9 ]", " ", name).split()


def is_generic_name(name: str) -> bool:
    """True when no token of the name is distinctive ('Final Laboratory', 'Services Inc.')."""
    distinct = [t for t in name_tokens(name) if t not in _GENERIC_WORDS]
    return not distinct or (len(distinct) == 1 and len(distinct[0]) < _MIN_DISTINCT_TOKEN_LEN)


# --- manual group assignments for company nodes ---------------------------------------
# entity_id -> (group, basis). Reviewed against the entity name and page text samples.
MANUAL_GROUPS = {
    "silverstein-properties": ("private_real_estate", "WTC site leaseholder / 7 WTC developer"),
    "rockrose-development": ("private_real_estate", "residential developer & landlord (Lower Manhattan)"),
    "related-management": ("private_real_estate", "Related Cos. property management arm"),
    "gateway-plaza-management": ("private_real_estate", "manager of Gateway Plaza residential complex (BPC)"),
    "milford-management": ("private_real_estate", "residential property manager"),
    "jack-resnick-and-sons": ("private_real_estate", "commercial real estate owner/developer"),
    "century-realty": ("private_real_estate", "'Realty' in name"),
    "duane-street-associates": ("private_real_estate", "building-owning partnership named for its street"),
    "maiden-lane-associates": ("private_real_estate", "building-owning partnership named for its street"),
    "financial-district-associates": ("private_real_estate", "building-owning partnership"),
    "broadway-associates": ("private_real_estate", "building-owning partnership named for its street"),
    "church-street-associates": ("private_real_estate", "building-owning partnership named for its street"),
    "park-place-associates": ("private_real_estate", "building-owning partnership named for its street"),
    "murray-street-associates": ("private_real_estate", "building-owning partnership named for its street"),
    "ann-street-associates": ("private_real_estate", "building-owning partnership named for its street"),
    "murray-warren-associates": ("private_real_estate", "building-owning partnership (Murray/Warren St.)"),
    "masterworks-development": ("private_real_estate", "private residential developer"),
    "block-hall-development": ("private_real_estate", "private developer"),
    # public bodies the site filed as contractors / labs
    "new-york-city-economic-development": ("city_other", "NYC Economic Development Corp. (public benefit corp.)"),
    "empire-state-development": ("state_federal_regional", "NY State economic development agency"),
    "nyc-school-construction": ("city_other", "NYC School Construction Authority"),
    "school-construction": ("city_other", "NYC School Construction Authority"),
    "lower-manhattan-redevelopment": ("state_federal_regional", "likely LMDC variant (name differs); state body"),
    "epa-laboratory": ("state_federal_regional", "U.S. EPA laboratory"),
    "epa-mobile-laboratory": ("state_federal_regional", "U.S. EPA laboratory"),
    "niosh-analytical": ("state_federal_regional", "NIOSH analytical methods/lab"),
    "niosh-pat-laboratory": ("state_federal_regional", "NIOSH PAT program"),
    # private, but not real estate
    "bovis-lend-lease-lmb": ("consultant_contractor_lab", "construction manager"),
    "ambassador-construction": ("consultant_contractor_lab", "construction contractor"),
    "liberty-mutual-insurance": ("other_unknown", "insurer"),
    "tsi": ("other_unknown", "instrument manufacturer (TSI Inc.)"),
    "air-conditioning-engineers": ("other_unknown", "fragment of ASHRAE (standards body), cited in IAQ reports; "
                                                    "found in the manual page check"),
    "rae-systems": ("other_unknown", "instrument manufacturer"),
    "warren-street-tenants": ("other_unknown", "residential co-op corporation (owner-occupants, not a real-estate firm)"),
    "cushman-and-wakefield": ("private_real_estate", "commercial real estate services firm"),
    "newmark-and": ("private_real_estate", "Newmark & Co. Real Estate (see newmark-and-real-estate)"),
    "atc-associates": ("consultant_contractor_lab", "ATC Associates: environmental consultant (asbestos/air surveys)"),
    "cosentini-associates": ("consultant_contractor_lab", "MEP engineering firm"),
    "rj-lee-group": ("consultant_contractor_lab", "materials-analysis lab / consultant (WTC dust studies)"),
    "ambient-group": ("consultant_contractor_lab", "environmental / industrial-hygiene consultant"),
    "riverpoint": ("consultant_contractor_lab", "Riverpoint Environmental Consultants (variant in entity table)"),
}

# manual assignments whose basis is an inference from the name, not outside knowledge
MANUAL_UNCERTAIN = {k for k, (_, basis) in MANUAL_GROUPS.items() if "named for its street" in basis} | {
    "financial-district-associates", "murray-warren-associates", "lower-manhattan-redevelopment",
    "newmark-and", "riverpoint"}

# conservative keyword rules (only when no manual entry)
# "X Owners Corp." / "X Tenants Corp." is the usual name of a resident-owned co-operative in NYC
_COOP_RE = re.compile(r"\b(owners|tenants)\s+(corp|corporation|inc)\b", re.I)
_REAL_ESTATE_RE = re.compile(r"\b(realty|real estate|properties|property|owners|landlord|apartments)\b", re.I)
_CONSULTANT_RE = re.compile(
    r"\b(environmental|environ|analytical|laborator\w*|labs?|engineer\w*|consult\w*|asbestos|abatement|"
    r"hygien\w*|testing|geotech\w*|remediation|contracting|construction|demolition|builders)\b", re.I)


def keyword_group(name: str) -> tuple[str, str]:
    if _COOP_RE.search(name):
        return "other_unknown", "residential co-operative (resident-owned), not a real-estate firm"
    if _REAL_ESTATE_RE.search(name):
        return "private_real_estate", "keyword: " + _REAL_ESTATE_RE.search(name).group(0).lower()
    if _CONSULTANT_RE.search(name):
        return "consultant_contractor_lab", "keyword: " + _CONSULTANT_RE.search(name).group(0).lower()
    return "other_unknown", "no rule matched"


def classify_nodes(nodes: pd.DataFrame) -> pd.DataFrame:
    """nodes needs node_id, node_kind ('agency'/'company'/'advocacy'), entity_id, name, agency_level.

    Returns node_id, entity_id, name, node_kind, group, group_label, basis, review_status.
    """
    rows = []
    for n in nodes.itertuples(index=False):
        if n.node_kind == "agency":
            if n.entity_id in MUNICIPAL_REGULATORY:
                group, basis = "municipal_regulatory", MUNICIPAL_REGULATORY[n.entity_id]
            else:
                group, basis = AGENCY_LEVEL_GROUP[n.agency_level], f"agency_map.py level = {n.agency_level}"
            status = "curated (agency_map.py + a-priori regulator list)"
        elif n.node_kind == "advocacy":
            group, basis, status = "public_health_advocacy", "fixed name list (text supplement)", "manual"
        elif n.entity_id in MANUAL_GROUPS:
            (group, basis), status = MANUAL_GROUPS[n.entity_id], "manual"
            if n.entity_id in MANUAL_UNCERTAIN:
                status = "manual (uncertain)"
        else:
            group, basis = keyword_group(n.name)
            status = "rule (unreviewed)" if group != "other_unknown" else "unclassified"
        rows.append((n.node_id, n.entity_id, n.name, n.node_kind, group, GROUP_LABELS[group], basis, status))
    return pd.DataFrame(rows, columns=["node_id", "entity_id", "name", "node_kind", "group",
                                       "group_label", "basis", "review_status"])
