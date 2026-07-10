import { useState } from "react";
import { listSnapshots } from "../../lib/providersApi";
import type { RunSnapshot } from "../../types/providers";

export function RunSnapshotViewer() {
  const [caseId, setCaseId] = useState("");
  const [snapshots, setSnapshots] = useState<RunSnapshot[]>([]);
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    if (!caseId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listSnapshots(caseId.trim());
      setSnapshots(data.snapshots || []);
      setStats(data.stats || null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleLoad();
  };

  return (
    <div className="snapshot-viewer">
      <h3>Run Snapshot Viewer</h3>
      <div className="snapshot-input-row">
        <input
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter case ID..."
        />
        <button onClick={handleLoad} disabled={loading || !caseId.trim()}>
          {loading ? "Loading..." : "Load"}
        </button>
      </div>

      {error && <div className="settings-error">{error}</div>}

      {stats && (
        <div className="snapshot-stats">
          <span>Total: {stats.total}</span>
          <span>Success: {stats.success}</span>
          <span>Failed: {stats.failure}</span>
          <span>Heuristic: {stats.heuristic_fallbacks}</span>
          <span>Repairs: {stats.total_repairs}</span>
        </div>
      )}

      {snapshots.length > 0 && (
        <table className="snapshot-table">
          <thead>
            <tr>
              <th>Contract</th>
              <th>Role</th>
              <th>Success</th>
              <th>Heuristic</th>
              <th>Providers</th>
              <th>Repairs</th>
              <th>Tokens In</th>
              <th>Tokens Out</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((s, i) => (
              <tr key={s.snapshot_id || i} className={s.success ? "snap-ok" : "snap-fail"}>
                <td>{s.contract_id}</td>
                <td>{s.contract_role}</td>
                <td>{s.success ? "✅" : "❌"}</td>
                <td>{s.heuristic ? "⚠" : "—"}</td>
                <td>{s.providers_tried}</td>
                <td>{s.repairs}</td>
                <td>{s.tokens_in}</td>
                <td>{s.tokens_out}</td>
                <td>{s.error || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!loading && snapshots.length === 0 && stats && (
        <p className="settings-empty">No snapshots found for this case.</p>
      )}
    </div>
  );
}
