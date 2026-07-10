import { useState, useEffect, useCallback } from "react";
import { listProviders, deleteProvider } from "../../lib/providersApi";
import type { ProviderProfile } from "../../types/providers";

interface Props {
  onEdit: (id: string) => void;
  refreshTrigger: number;
}

export function ProviderProfiles({ onEdit, refreshTrigger }: Props) {
  const [providers, setProviders] = useState<ProviderProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProviders();
      setProviders(data.providers || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load, refreshTrigger]);

  const handleDelete = async (id: string) => {
    if (!confirm(`Delete provider? Secrets will be removed.`)) return;
    setDeleting(id);
    try {
      await deleteProvider(id);
      setProviders((p) => p.filter((x) => x.provider_id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(null);
    }
  };

  if (loading) return <div className="settings-loading">Loading providers...</div>;
  if (error) return <div className="settings-error">{error}</div>;

  const statusIcon = (s: string) => {
    switch (s) {
      case "active": return <span className="status-dot status-active" title="Active">●</span>;
      case "invalid": return <span className="status-dot status-invalid" title="Invalid">●</span>;
      case "disabled": return <span className="status-dot status-disabled" title="Disabled">●</span>;
      default: return null;
    }
  };

  return (
    <div className="provider-list">
      <h3>Provider Profiles</h3>
      {providers.length === 0 && (
        <p className="settings-empty">No providers configured. Use the wizard to add one.</p>
      )}
      {providers.map((p) => (
        <div key={p.provider_id} className={`provider-card status-${p.status}`}>
          <div className="provider-card-header">
            {statusIcon(p.status)}
            <strong>{p.label}</strong>
            <span className="provider-protocol">{p.protocol}</span>
          </div>
          <div className="provider-card-body">
            <div>Models: {p.models?.length || 0}</div>
            <div>Secret: {p.api_key_set ? "key set" : "no key"}</div>
            <div>Storage: {p.secret_type}</div>
            <div className="provider-card-actions">
              <button onClick={() => onEdit(p.provider_id)}>Edit</button>
              <button
                onClick={() => handleDelete(p.provider_id)}
                disabled={deleting === p.provider_id}
              >
                {deleting === p.provider_id ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
