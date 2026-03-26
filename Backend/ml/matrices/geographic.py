"""
Geographic proximity matrix builder — same-region artists score higher.

Scoring:
  same country   = 0.5
  same region     = 0.25
  different region = 0.0
  missing country  = 0.1 (neutral)
"""
from __future__ import annotations

import numpy as np

from ml.data_exporter import GraphExport

# ISO country code -> region mapping
COUNTRY_TO_REGION: dict[str, str] = {
    # North America
    "US": "north_america", "CA": "north_america", "MX": "north_america",
    # Central America & Caribbean
    "JM": "caribbean", "TT": "caribbean", "CU": "caribbean", "PR": "caribbean",
    "DO": "caribbean", "HT": "caribbean",
    # South America
    "BR": "south_america", "AR": "south_america", "CO": "south_america",
    "CL": "south_america", "VE": "south_america", "PE": "south_america",
    "EC": "south_america", "UY": "south_america",
    # Western Europe
    "GB": "europe_west", "IE": "europe_west", "FR": "europe_west",
    "DE": "europe_west", "NL": "europe_west", "BE": "europe_west",
    "AT": "europe_west", "CH": "europe_west", "LU": "europe_west",
    # Northern Europe
    "SE": "europe_north", "NO": "europe_north", "DK": "europe_north",
    "FI": "europe_north", "IS": "europe_north",
    # Southern Europe
    "IT": "europe_south", "ES": "europe_south", "PT": "europe_south",
    "GR": "europe_south",
    # Eastern Europe
    "PL": "europe_east", "CZ": "europe_east", "SK": "europe_east",
    "HU": "europe_east", "RO": "europe_east", "BG": "europe_east",
    "HR": "europe_east", "RS": "europe_east", "SI": "europe_east",
    "UA": "europe_east", "BY": "europe_east", "RU": "europe_east",
    # East Asia
    "JP": "east_asia", "KR": "east_asia", "CN": "east_asia",
    "TW": "east_asia", "HK": "east_asia",
    # Southeast Asia
    "TH": "southeast_asia", "VN": "southeast_asia", "PH": "southeast_asia",
    "ID": "southeast_asia", "MY": "southeast_asia", "SG": "southeast_asia",
    # South Asia
    "IN": "south_asia", "PK": "south_asia", "BD": "south_asia",
    "LK": "south_asia",
    # Middle East
    "IL": "middle_east", "TR": "middle_east", "IR": "middle_east",
    "SA": "middle_east", "AE": "middle_east", "LB": "middle_east",
    # Africa
    "ZA": "africa", "NG": "africa", "KE": "africa", "GH": "africa",
    "ET": "africa", "TZ": "africa", "SN": "africa", "ML": "africa",
    "EG": "africa", "MA": "africa", "DZ": "africa", "TN": "africa",
    # Oceania
    "AU": "oceania", "NZ": "oceania",
}

MISSING_COUNTRY_SCORE = 0.1
SAME_COUNTRY_SCORE = 0.5
SAME_REGION_SCORE = 0.25
DIFFERENT_REGION_SCORE = 0.0


def _get_region(country: str | None) -> str | None:
    """Look up the region for a country code."""
    if not country:
        return None
    return COUNTRY_TO_REGION.get(country.upper())


def build_geographic_matrix(graph_export: GraphExport) -> np.ndarray:
    """
    Build an NxN geographic proximity matrix.

    Diagonal is 1.0 (same artist = same location).
    """
    n = graph_export.n
    matrix = np.zeros((n, n), dtype=np.float64)

    # Pre-compute countries and regions
    countries = [artist.country for artist in graph_export.artists]
    regions = [_get_region(c) for c in countries]

    for i in range(n):
        matrix[i][i] = 1.0  # Self-similarity

        for j in range(i + 1, n):
            c_i, c_j = countries[i], countries[j]
            r_i, r_j = regions[i], regions[j]

            # Either country missing
            if not c_i or not c_j:
                score = MISSING_COUNTRY_SCORE
            # Same country
            elif c_i.upper() == c_j.upper():
                score = SAME_COUNTRY_SCORE
            # Same region
            elif r_i and r_j and r_i == r_j:
                score = SAME_REGION_SCORE
            # Different region (or unmapped countries)
            else:
                score = DIFFERENT_REGION_SCORE

            matrix[i][j] = score
            matrix[j][i] = score

    return matrix
