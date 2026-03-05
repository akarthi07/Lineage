"""
Sub-task 1.10 — Test the full seed → query pipeline.

Run from the Backend/ directory:
    python scripts/seed_test.py

Requires: Neo4j + Redis running (docker compose up -d from project root)
          .env file with API keys
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services import graph_manager as gm
from services.artist_seeder import seed_artist_network

TEST_ARTISTS = ["Radiohead", "Portishead", "Björk"]


def main():
    print("=" * 60)
    print("LINEAGE — Seed + Query Pipeline Test")
    print("=" * 60)

    gm.ensure_indexes()

    for artist_name in TEST_ARTISTS:
        print(f"\n{'─' * 50}")
        print(f"Seeding: {artist_name} (depth=1)")
        print("─" * 50)
        root = seed_artist_network(artist_name, depth=1)
        if not root:
            print(f"FAILED to seed {artist_name}")
            continue

        print(f"\n✅ Seeded {root.name}")
        print(f"   MBID: {root.mbid}")
        print(f"   Last.fm listeners: {root.lastfm_listeners:,}" if root.lastfm_listeners else "   Last.fm listeners: N/A")
        print(f"   Underground score: {root.underground_score:.2f}")
        print(f"   Tags: {', '.join(root.tags[:5])}")

        if root.mbid:
            print(f"\n  Querying lineage (depth=2, balanced)...")
            result = gm.get_lineage(root.mbid, direction="backward", depth=2, underground_level="balanced")
            print(f"  Nodes: {result.metadata['total_nodes']}")
            print(f"  Edges: {len(result.edges)}")
            print(f"  Underground %: {result.metadata['underground_percentage']:.0%}")
            if result.nodes:
                print(f"  Sample nodes:")
                for node in result.nodes[:5]:
                    print(f"    - {node.name} (score={node.underground_score:.2f}, depth={node.depth_level})")

    print(f"\n{'=' * 60}")
    print("Done. Check Neo4j Browser at http://localhost:7474")
    print("Query: MATCH (a:Artist) RETURN a LIMIT 50")
    gm.close_driver()


if __name__ == "__main__":
    main()
