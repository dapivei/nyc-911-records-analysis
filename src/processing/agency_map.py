"""Hand-curated mapping of the site's 46 agency slugs to canonical agencies.

The site lists the same agency under several slugs (e.g. "dep" and
"department-of-environmental-protection"). Merging them keeps one node per
organization in the RQ1 network. `level` groups agencies for Hypothesis 1:
city / state / federal / regional (bi-state) / private / nonprofit.

To change a mapping, edit AGENCIES below; every slug must appear exactly once.
"""

# entity_id: (entity_name, level, [site slugs merged into it])
AGENCIES = {
    "nyc-dep": ("NYC Dept. of Environmental Protection", "city",
                ["dep", "department-of-environmental-protection"]),
    "nyc-dohmh": ("NYC Dept. of Health and Mental Hygiene", "city",
                  ["doh", "department-of-health", "dohmh"]),
    "nyc-dob": ("NYC Dept. of Buildings", "city", ["dob", "department-of-buildings"]),
    "nyc-doe": ("NYC Board of Education", "city", ["board-of-education"]),
    "nyc-oem": ("NYC Office of Emergency Management", "city",
                ["oem", "office-of-emergency-management"]),
    "nyc-dcas": ("NYC Dept. of Citywide Administrative Services", "city", ["dcas"]),
    "nyc-mayor": ("NYC Office of the Mayor", "city", ["mayor-s-office", "office-of-the-mayor", "city-hall"]),
    "nyc-law": ("NYC Law Department", "city", ["law-department", "corporation-counsel"]),
    "nyc-fdny": ("FDNY", "city", ["fdny", "fire-department"]),
    "nyc-nypd": ("NYPD", "city", ["nypd", "police-department"]),
    "nyc-ddc": ("NYC Dept. of Design and Construction", "city",
                ["ddc", "department-of-design-and-construction"]),
    "nyc-dsny": ("NYC Dept. of Sanitation", "city", ["dsny", "department-of-sanitation"]),
    "nyc-hpd": ("NYC Dept. of Housing Preservation and Development", "city", ["hpd"]),
    "nyc-doris": ("NYC Dept. of Records and Information Services", "city", ["doris"]),
    "nys-doh": ("NYS Dept. of Health", "state", ["nysdoh"]),
    "nys-dec": ("NYS Dept. of Environmental Conservation", "state", ["nysdec"]),
    "lmdc": ("Lower Manhattan Development Corporation", "state",
             ["lmdc", "lower-manhattan-development-corporation",
              "lower-manhattan-development-corp", "the-lower-manhattan-development-corp"]),
    "bpca": ("Battery Park City Authority", "state", ["battery-park-city-authority"]),
    "port-authority": ("Port Authority of NY & NJ", "regional", ["port-authority"]),
    "us-epa": ("U.S. EPA", "federal", ["epa", "environmental-protection-agency", "u-s-epa"]),
    "us-osha": ("OSHA", "federal", ["osha"]),
    "us-niosh": ("NIOSH", "federal", ["niosh"]),
    "us-atsdr": ("ATSDR", "federal", ["atsdr"]),
    "us-cdc": ("CDC", "federal", ["cdc"]),
    "us-fema": ("FEMA", "federal", ["fema"]),
    "us-usace": ("U.S. Army Corps of Engineers", "federal", ["army-corps-of-engineers", "usace"]),
    "con-edison": ("Con Edison", "private", ["con-edison"]),
    "verizon": ("Verizon", "private", ["verizon"]),
    "red-cross": ("American Red Cross", "nonprofit", ["red-cross"]),
    "salvation-army": ("Salvation Army", "nonprofit", ["salvation-army"]),
}


# Public bodies the site filed as contractors (the "Corp." in the name looks like
# a company). clean.py moves these entity rows to entity_type "agency".
CONTRACTOR_SLUGS_THAT_ARE_AGENCIES = {
    "lower-manhattan-development-corp",
    "the-lower-manhattan-development-corp",
}


def agency_lookup():
    """Return {site_slug: (entity_id, entity_name, level)}."""
    lookup = {}
    for entity_id, (name, level, slugs) in AGENCIES.items():
        for slug in slugs:
            if slug in lookup:
                raise ValueError(f"agency slug {slug!r} is mapped twice")
            lookup[slug] = (entity_id, name, level)
    return lookup
