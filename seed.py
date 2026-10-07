"""Starter institution list.

Public framing: this is a *user-provided starter list*, not a verified ranking.
The variable name is preserved exactly as supplied. Always compute
``len(top_100_us_universities)`` — do not assume the count from the name.
"""
from __future__ import annotations

top_100_us_universities = [
    "Massachusetts Institute of Technology",
    "Stanford University",
    "Harvard University",
    "California Institute of Technology",
    "University of Pennsylvania",
    "Cornell University",
    "Yale University",
    "Johns Hopkins University",
    "University of California, Berkeley",
    "University of Chicago",
    "Princeton University",
    "Columbia University",
    "Northwestern University",
    "University of California, Los Angeles",
    "University of Michigan-Ann Arbor",
    "Carnegie Mellon University",
    "New York University",
    "Brown University",
    "Duke University",
    "University of Texas at Austin",
    "University of Illinois Urbana-Champaign",
    "University of California, San Diego",
    "Pennsylvania State University",
    "University of Washington",
    "Boston University",
    "Purdue University",
    "Rice University",
    "University of Wisconsin-Madison",
    "University of California, Davis",
    "Georgia Institute of Technology",
    "University of Southern California",
    "University of North Carolina at Chapel Hill",
    "Washington University in St. Louis",
    "Texas A&M University",
    "Arizona State University",
    "University of California, Santa Barbara",
    "Michigan State University",
    "Emory University",
    "Ohio State University",
    "University of Florida",
    "University of Rochester",
    "University of California, Irvine",
    "University of Maryland, College Park",
    "University of Minnesota (System)",
    "University of Massachusetts Amherst",
    "Vanderbilt University",
    "University of Virginia",
    "Dartmouth College",
    "University of Pittsburgh",
    "Georgetown University",
    "University of Notre Dame",
    "University of Arizona",
    "Rutgers University-New Brunswick",
    "North Carolina State University",
    "University of Colorado Boulder",
    "Case Western Reserve University",
    "Tufts University",
    "University of Miami",
    "Indiana University Bloomington",
    "Virginia Polytechnic Institute and State University",
    "University of Illinois Chicago",
    "George Washington University",
    "Northeastern University",
    "University of California, Riverside",
    "University at Buffalo SUNY",
    "University of California, Santa Cruz",
    "University of Connecticut",
    "Stony Brook University, State University of New York",
    "Washington State University",
    "University of Kansas",
    "University of Utah",
    "University of Georgia",
    "Colorado State University",
    "Iowa State University",
    "Florida State University",
    "Boston College",
    "University of Houston",
    "Colorado School of Mines",
    "University of Delaware",
    "Rensselaer Polytechnic Institute",
    "Tulane University",
    "University of Iowa",
    "Illinois Institute of Technology",
    "University of Hawaiʻi at Mānoa",
    "American University",
    "Florida International University",
    "Lehigh University",
    "Stevens Institute of Technology",
    "City University of New York",
    "University of Texas at Dallas",
    "University of Tennessee, Knoxville",
    "Oregon State University",
    "University of Oregon",
    "University of South Carolina",
    "University of Missouri, Columbia",
    "Syracuse University",
    "University of Central Florida",
    "New Jersey Institute of Technology",
    "University of Cincinnati",
    "Brandeis University",
]

# Ambiguous identities that must NOT be silently substituted.
# A CDS returned for a system must be mapped only via reviewed mapping
# or surfaced as needing clarification.
AMBIGUOUS_IDENTITIES: dict[str, str] = {
    "University of Minnesota (System)": (
        "System entry: CDS is published per campus (Twin Cities, Duluth, "
        "Morris, Crookston, Rochester). Requires reviewed campus mapping."
    ),
    "City University of New York": (
        "System entry: CDS is published per college (e.g. Baruch, Hunter, "
        "City College, Queens). Requires reviewed college mapping."
    ),
}

# Other multi-campus names that deserve a caution flag even when a single
# campus CDS is commonly returned.
MULTI_CAMPUS_NOTES: dict[str, str] = {
    "University of California, Berkeley": "UC system campus; verify Berkeley CDS, not system-wide.",
    "University of California, Los Angeles": "UC system campus; verify UCLA CDS.",
    "University of California, San Diego": "UC system campus; verify UCSD CDS.",
    "University of California, Davis": "UC system campus; verify UCD CDS.",
    "University of California, Santa Barbara": "UC system campus; verify UCSB CDS.",
    "University of California, Irvine": "UC system campus; verify UCI CDS.",
    "University of California, Riverside": "UC system campus; verify UCR CDS.",
    "University of California, Santa Cruz": "UC system campus; verify UCSC CDS.",
    "Pennsylvania State University": "Multi-campus; main CDS is University Park unless stated.",
    "Rutgers University-New Brunswick": "Verify New Brunswick campus CDS specifically.",
    "University of Texas at Austin": "UT System campus; verify Austin CDS.",
    "University of Texas at Dallas": "UT System campus; verify Dallas CDS.",
}


def starter_list_count() -> int:
    """Actual entry count — never assume 100 from the variable name."""
    return len(top_100_us_universities)


def ambiguity_note(name: str) -> str | None:
    if name in AMBIGUOUS_IDENTITIES:
        return AMBIGUOUS_IDENTITIES[name]
    return MULTI_CAMPUS_NOTES.get(name)
