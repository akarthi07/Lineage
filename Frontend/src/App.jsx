import { Routes, Route, useNavigate } from "react-router-dom";
import Layout from "./components/shared/Layout";
import DiscoveryFeed from "./views/DiscoveryFeed";
import LineageView from "./views/LineageView";
import GenesisView from "./views/GenesisView";
import { useLineageQuery } from "./hooks/useLineageQuery";

export default function App() {
  const navigate = useNavigate();
  const { data, seeding, seedingArtist, searchTerm, loading, query } = useLineageQuery();

  const handleSearch = (artistName, options = {}) => {
    query(artistName, options);
    navigate("/lineage");
  };

  return (
    <Layout>
      <Routes>
        <Route
          path="/"
          element={<DiscoveryFeed onSearch={handleSearch} loading={loading} />}
        />
        <Route
          path="/lineage"
          element={
            <LineageView
              data={data}
              seeding={seeding}
              artistName={seedingArtist}
              searchTerm={searchTerm}
              onSearch={handleSearch}
              loading={loading}
            />
          }
        />
        <Route path="/genesis" element={<GenesisView />} />
      </Routes>
    </Layout>
  );
}
