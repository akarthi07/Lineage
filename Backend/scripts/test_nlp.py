"""
Test script for the Claude NLP layer (Chunk 2).
Tests parsing across all query types.

Usage:
    cd Backend
    source venv/Scripts/activate
    python scripts/test_nlp.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from services.nlp_client import parse_query, resolve_discovery

# ---------------------------------------------------------------------------
# Test queries grouped by expected type
# ---------------------------------------------------------------------------
TEST_QUERIES = {
    "artist_lineage": [
        "who influenced Radiohead",
        "where does Playboi Carti's sound come from",
        "show me the lineage of Burial",
        "what are Kanye West's musical roots",
        "trace MF DOOM's influences",
    ],
    "discovery": [
        "find me something like Bladee but darker",
        "weird ambient stuff from Japan",
        "underground Detroit techno producers",
        "something like Aphex Twin but more chill",
        "I want aggressive lo-fi hip hop",
    ],
    "genesis": [
        "how did drill music start",
        "trace the roots of shoegaze",
        "where did plugg production come from",
        "origins of vaporwave",
        "how did UK garage evolve",
    ],
    "connection": [
        "how are MF DOOM and Madlib connected",
        "link between Aphex Twin and Autechre",
        "what's the connection from The Beatles to Tame Impala",
        "how does Kanye relate to Kid Cudi",
    ],
    "clarification_needed": [
        "music",
        "uhhhh",
        "play something",
    ],
}


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        print("Add your key to Backend/.env and retry.")
        sys.exit(1)

    total = 0
    correct = 0
    errors = 0

    for expected_type, queries in TEST_QUERIES.items():
        print(f"\n{'='*60}")
        print(f"  Testing: {expected_type}")
        print(f"{'='*60}")

        for q in queries:
            total += 1
            try:
                parsed = parse_query(q)
                match = "OK" if parsed.query_type == expected_type else "MISMATCH"
                if match == "OK":
                    correct += 1

                print(f"\n  Query: \"{q}\"")
                print(f"  Type:  {parsed.query_type} [{match}]")
                print(f"  Artists: {parsed.artist_names}")
                print(f"  Direction: {parsed.direction} | Depth: {parsed.depth}")
                if parsed.musical_characteristics:
                    print(f"  Characteristics: {parsed.musical_characteristics}")
                if parsed.modifiers:
                    print(f"  Modifiers: {parsed.modifiers}")
                if parsed.clarification_question:
                    print(f"  Clarification: {parsed.clarification_question}")

                # Test discovery resolution for discovery queries
                if parsed.query_type == "discovery":
                    discovery = resolve_discovery(parsed)
                    print(f"  Discovery tags: {discovery.get('search_tags', [])}")
                    print(f"  Seed artists: {discovery.get('seed_artists', [])}")
                    print(f"  Explanation: {discovery.get('explanation', '')}")

            except Exception as exc:
                errors += 1
                print(f"\n  Query: \"{q}\"")
                print(f"  ERROR: {exc}")

    print(f"\n{'='*60}")
    print(f"  Results: {correct}/{total} correct type, {errors} errors")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
