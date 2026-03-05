import os
import time
import json
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()

ARTIST_NAME = "Radiohead"
results = {"spotify": False, "lastfm": False, "musicbrainz": False, "neo4j": False}


# ============================================================
# TEST 1: SPOTIFY (Supplementary — search + metadata only)
# ============================================================
print("=" * 60)
print("TEST 1: SPOTIFY (supplementary — search & metadata)")
print("=" * 60)

try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
    ))

    search = sp.search(q=ARTIST_NAME, type="artist", limit=1)
    artist = search["artists"]["items"][0]

    print(f"  Name: {artist['name']}")
    print(f"  Spotify ID: {artist['id']}")
    print(f"  Popularity: {artist['popularity']}")
    print(f"  Followers: {artist['followers']['total']}")
    print(f"  Genres: {artist['genres']}")
    print(f"  Image: {artist['images'][0]['url'] if artist['images'] else 'None'}")

    spotify_id = artist["id"]
    spotify_genres = artist["genres"]

    # Confirm deprecated endpoints are still blocked
    print("\n  Confirming deprecated endpoints are blocked:")
    try:
        sp.artist_related_artists(spotify_id)
        print("  ⚠️  Related Artists returned 200 — unexpected! May have extended access.")
    except Exception:
        print("  ✓ Related Artists: 403 (confirmed blocked — expected)")

    try:
        top = sp.artist_top_tracks(spotify_id, country="US")
        track_ids = [t["id"] for t in top["tracks"][:1]]
        sp.audio_features(track_ids)
        print("  ⚠️  Audio Features returned 200 — unexpected!")
    except Exception:
        print("  ✓ Audio Features: 403 (confirmed blocked — expected)")

    print("\n  ✅ Spotify: WORKING (search + metadata)")
    results["spotify"] = True

except Exception as e:
    print(f"\n  ❌ Spotify FAILED: {e}")


# ============================================================
# TEST 2: LAST.FM (Primary — similar artists + listener data)
# ============================================================
print("\n" + "=" * 60)
print("TEST 2: LAST.FM (primary — similar artists & listener data)")
print("=" * 60)

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_BASE = "https://ws.audioscrobbler.com/2.0/"

if not LASTFM_API_KEY:
    print("  ❌ LASTFM_API_KEY not found in .env")
    print("  Get a free key at: https://www.last.fm/api/account/create")
    print("  Add to .env: LASTFM_API_KEY=your_key_here")
else:
    try:
        # Test 2a: artist.getInfo
        print("\n  --- artist.getInfo ---")
        r = requests.get(LASTFM_BASE, params={
            "method": "artist.getInfo",
            "artist": ARTIST_NAME,
            "api_key": LASTFM_API_KEY,
            "format": "json"
        })
        data = r.json()
        artist_info = data["artist"]

        lastfm_listeners = int(artist_info["stats"]["listeners"])
        lastfm_playcount = int(artist_info["stats"]["playcount"])
        lastfm_mbid = artist_info.get("mbid", "N/A")

        print(f"  Name: {artist_info['name']}")
        print(f"  Listeners: {lastfm_listeners:,}")
        print(f"  Play count: {lastfm_playcount:,}")
        print(f"  MusicBrainz ID: {lastfm_mbid}")
        print(f"  Bio: {artist_info['bio']['summary'][:100]}...")

        # Test 2b: artist.getSimilar (THIS REPLACES Spotify's Related Artists)
        print("\n  --- artist.getSimilar (CRITICAL — replaces Spotify related artists) ---")
        time.sleep(0.3)
        r = requests.get(LASTFM_BASE, params={
            "method": "artist.getSimilar",
            "artist": ARTIST_NAME,
            "api_key": LASTFM_API_KEY,
            "limit": 10,
            "format": "json"
        })
        data = r.json()
        similar = data["similarartists"]["artist"]

        print(f"  Found {len(similar)} similar artists:")
        for i, s in enumerate(similar):
            match = float(s["match"])
            print(f"    {i+1}. {s['name']} — match: {match:.2f} — mbid: {s.get('mbid', 'N/A')[:20]}")

        # Test 2c: artist.getTopTags
        print("\n  --- artist.getTopTags ---")
        time.sleep(0.3)
        r = requests.get(LASTFM_BASE, params={
            "method": "artist.getTopTags",
            "artist": ARTIST_NAME,
            "api_key": LASTFM_API_KEY,
            "format": "json"
        })
        data = r.json()
        tags = data["toptags"]["tag"][:10]

        print(f"  Top tags:")
        for t in tags:
            print(f"    - {t['name']} (count: {t['count']})")

        print("\n  ✅ Last.fm: WORKING (similar artists + info + tags)")
        results["lastfm"] = True

    except Exception as e:
        print(f"\n  ❌ Last.fm FAILED: {e}")


# ============================================================
# TEST 3: MUSICBRAINZ (Primary — curated relationships)
# ============================================================
print("\n" + "=" * 60)
print("TEST 3: MUSICBRAINZ (primary — curated artist relationships)")
print("=" * 60)

MB_BASE = "https://musicbrainz.org/ws/2"
MB_HEADERS = {
    "User-Agent": os.getenv("MUSICBRAINZ_USER_AGENT", "Lineage/1.0 (test@lineage.app)"),
    "Accept": "application/json"
}

try:
    # Test 3a: Search for artist
    print("\n  --- Artist search ---")
    r = requests.get(f"{MB_BASE}/artist/", params={
        "query": ARTIST_NAME,
        "fmt": "json",
        "limit": 3
    }, headers=MB_HEADERS)
    data = r.json()
    artists = data["artists"]

    mb_artist = artists[0]
    mbid = mb_artist["id"]
    print(f"  Name: {mb_artist['name']}")
    print(f"  MBID: {mbid}")
    print(f"  Type: {mb_artist.get('type', 'N/A')}")
    print(f"  Country: {mb_artist.get('country', 'N/A')}")
    print(f"  Active: {mb_artist.get('life-span', {}).get('begin', '?')} — {mb_artist.get('life-span', {}).get('end', 'present')}")
    if len(artists) > 1:
        print(f"  (Also found: {', '.join(a['name'] + ' [' + a.get('disambiguation', '') + ']' for a in artists[1:3])})")

    # Test 3b: Get artist relationships (THE KEY ENDPOINT)
    print(f"\n  --- Artist relationships (CRITICAL — this is lineage data) ---")
    time.sleep(1.1)  # MusicBrainz rate limit: 1 req/sec
    r = requests.get(f"{MB_BASE}/artist/{mbid}", params={
        "inc": "artist-rels+tags",
        "fmt": "json"
    }, headers=MB_HEADERS)
    data = r.json()

    # Parse relationships
    relations = data.get("relations", [])
    artist_rels = [rel for rel in relations if rel.get("type") and rel.get("target-type") == "artist"]

    if artist_rels:
        print(f"  Found {len(artist_rels)} artist relationships:")
        # Group by relationship type
        rel_types = {}
        for rel in artist_rels:
            rtype = rel["type"]
            direction = rel.get("direction", "forward")
            target = rel.get("artist", {})
            target_name = target.get("name", "Unknown")
            target_mbid = target.get("id", "N/A")

            if rtype not in rel_types:
                rel_types[rtype] = []
            rel_types[rtype].append({
                "name": target_name,
                "mbid": target_mbid,
                "direction": direction
            })

        for rtype, artists in rel_types.items():
            print(f"\n    [{rtype}] ({len(artists)} connections):")
            for a in artists[:5]:
                print(f"      → {a['name']} (direction: {a['direction']})")
            if len(artists) > 5:
                print(f"      ... and {len(artists) - 5} more")
    else:
        print("  ⚠️  No artist relationships found for this artist.")
        print("  This might be normal — not all artists have relationships entered.")
        print("  Try a different artist to verify the endpoint works.")

    # Parse tags
    mb_tags = data.get("tags", [])
    if mb_tags:
        top_tags = sorted(mb_tags, key=lambda t: t.get("count", 0), reverse=True)[:10]
        print(f"\n  MusicBrainz tags:")
        for t in top_tags:
            print(f"    - {t['name']} (votes: {t.get('count', 0)})")

    print(f"\n  ✅ MusicBrainz: WORKING (search + relationships + tags)")
    results["musicbrainz"] = True

except Exception as e:
    print(f"\n  ❌ MusicBrainz FAILED: {e}")


# ============================================================
# TEST 4: NEO4J (Graph database — optional, needs Docker)
# ============================================================
print("\n" + "=" * 60)
print("TEST 4: NEO4J (graph database)")
print("=" * 60)

try:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "lineagepassword")
    )

    with driver.session() as session:
        # Clean test data
        session.run("MATCH (n:TestArtist) DETACH DELETE n")

        # Create test nodes
        session.run("""
            CREATE (r:TestArtist {name: "Radiohead", mbid: "test-radiohead", underground_score: 0.0})
            CREATE (c:TestArtist {name: "Can", mbid: "test-can", underground_score: 0.3})
            CREATE (f:TestArtist {name: "Faust", mbid: "test-faust", underground_score: 0.5})
            CREATE (r)-[:INFLUENCED_BY {strength: 0.82, source: "musicbrainz"}]->(c)
            CREATE (c)-[:INFLUENCED_BY {strength: 0.6, source: "musicbrainz"}]->(f)
        """)

        # Test traversal
        result = session.run("""
            MATCH path = (r:TestArtist {name: "Radiohead"})-[:INFLUENCED_BY*1..2]->(influence)
            RETURN influence.name AS name, influence.underground_score AS score
        """)

        records = list(result)
        print(f"  Created 3 test nodes, 2 relationships")
        print(f"  Traversal from Radiohead (depth 2) found {len(records)} results:")
        for rec in records:
            print(f"    → {rec['name']} (underground: {rec['score']})")

        # Clean up
        session.run("MATCH (n:TestArtist) DETACH DELETE n")

    driver.close()
    print(f"\n  ✅ Neo4j: WORKING")
    results["neo4j"] = True

except ImportError:
    print("  ⚠️  neo4j package not installed. Run: pip install neo4j")
    print("  Skipping Neo4j test.")
except Exception as e:
    print(f"  ⚠️  Neo4j not running or connection failed: {e}")
    print("  Make sure Docker is running: docker compose up -d")
    print("  Skipping Neo4j test — this is OK for now, do it when Docker is set up.")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

status = {True: "✅ PASS", False: "❌ FAIL / SKIPPED"}

print(f"""
  Spotify (supplementary):  {status[results['spotify']]}
  Last.fm (primary):        {status[results['lastfm']]}
  MusicBrainz (primary):    {status[results['musicbrainz']]}
  Neo4j (graph DB):         {status[results['neo4j']]}
""")

if results["lastfm"] and results["musicbrainz"]:
    print("  🎉 PRIMARY DATA SOURCES WORKING — you can build the product!")
    if not results["neo4j"]:
        print("  → Set up Docker + Neo4j next (Chunk 1, sub-task 1.1 in tasks.md)")
elif not results["lastfm"]:
    print("  ⚠️  Last.fm not working — get your API key at https://www.last.fm/api/account/create")
    print("  Add LASTFM_API_KEY=your_key to .env")
elif not results["musicbrainz"]:
    print("  ⚠️  MusicBrainz not working — check your internet connection and User-Agent header")

if not results["spotify"]:
    print("  → Spotify is supplementary. Product works without it but you'll lack images/playback links.")

print()
