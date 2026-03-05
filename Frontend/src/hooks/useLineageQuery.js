import { useState, useCallback } from "react";
import { mockRadioheadLineage } from "../data/mockRadiohead";
import { mockUndergroundLineage } from "../data/mockUnderground";

const USE_MOCK = true; // flip to false when backend is running

export function useLineageQuery() {
  const [data, setData] = useState(null);
  const [seeding, setSeeding] = useState(false);
  const [seedingArtist, setSeedingArtist] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const query = useCallback(async (artistName, options = {}) => {
    setLoading(true);
    setError(null);
    setSeeding(false);

    if (USE_MOCK) {
      // Simulate network delay
      await new Promise((r) => setTimeout(r, 800));
      const lower = artistName.toLowerCase();
      if (lower.includes("radiohead") || lower.includes("joy") || lower.includes("talk talk")) {
        setData(mockRadioheadLineage);
      } else {
        setData(mockUndergroundLineage);
      }
      setLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: artistName,
          depth: options.depth ?? 3,
          underground_level: options.undergroundLevel ?? "balanced",
        }),
      });

      const json = await res.json();

      if (!res.ok) {
        throw new Error(json.detail ?? "Query failed");
      }

      if (json.status === "seeding_in_progress") {
        setSeeding(true);
        setSeedingArtist(json.artist_name ?? artistName);
        setData(null);
      } else {
        setSeeding(false);
        setData(json);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, seeding, seedingArtist, loading, error, query };
}
