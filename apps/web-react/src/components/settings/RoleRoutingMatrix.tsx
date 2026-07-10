import { useState, useEffect } from "react";
import { listPolicies, updatePolicy } from "../../lib/providersApi";
import { TASK_ROLE_LABELS, TASK_ROLE_DESCRIPTIONS, ALLOWED_MODEL_IDS } from "../../types/providers";
import type { ModelPolicyItem, TaskRole } from "../../types/providers";

export function RoleRoutingMatrix() {
  const [policies, setPolicies] = useState<ModelPolicyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Record<string, Partial<ModelPolicyItem>>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await listPolicies();
      setPolicies(data.policies || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async (role: TaskRole) => {
    const edits = editing[role];
    const orig = policies.find((p) => p.role === role);
    if (!edits || !orig) return;

    const updated: ModelPolicyItem = { ...orig, ...edits };
    setSaving(role);
    try {
      await updatePolicy(updated);
      setPolicies((prev) => prev.map((p) => (p.role === role ? updated : p)));
      setEditing((prev) => { const n = { ...prev }; delete n[role]; return n; });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(null);
    }
  };

  const getEdit = (role: TaskRole, field: keyof ModelPolicyItem) => {
    const e = editing[role];
    if (e && field in e) return e[field];
    const p = policies.find((x) => x.role === role);
    return p ? p[field] : undefined;
  };

  const setEdit = (role: TaskRole, patch: Partial<ModelPolicyItem>) => {
    setEditing((prev) => ({
      ...prev,
      [role]: { ...(prev[role] || {}), ...patch },
    }));
  };

  if (loading) return <div className="settings-loading">Loading policies...</div>;
  if (error) return <div className="settings-error">{error}</div>;

  const roles = Object.keys(TASK_ROLE_LABELS) as TaskRole[];

  const hasSelfReview = () => {
    const novelty = policies.find((p) => p.role === "novelty_draft");
    const critic = policies.find((p) => p.role === "evidence_critic");
    if (!novelty || !critic) return false;
    const np = getEdit("novelty_draft", "primary") as { model_id?: string } | undefined;
    const cp = getEdit("evidence_critic", "primary") as { model_id?: string } | undefined;
    const nm = np?.model_id || novelty.primary.model_id;
    const cm = cp?.model_id || critic.primary.model_id;
    return nm === cm;
  };

  return (
    <div className="role-matrix">
      <h3>Role Routing Matrix</h3>
      {hasSelfReview() && (
        <div className="settings-warning">
          ⚠ Self-review: novelty_draft and evidence_critic share the same model. Consider using different models for reviewer independence.
        </div>
      )}
      <div className="matrix-table-wrapper">
        <table className="matrix-table">
          <thead>
            <tr>
              <th>Role</th>
              <th>Description</th>
              <th>Primary</th>
              <th>Fallback</th>
              <th>Temp</th>
              <th>Heuristic</th>
              <th>Contract</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => {
              const primaryVal = getEdit(role, "primary") as { model_id?: string } | undefined;
              const primaryModelId = primaryVal?.model_id || policies.find((p) => p.role === role)?.primary.model_id || "";
              const fallbackVal = getEdit(role, "fallbacks") as Array<{ model_id?: string }> | undefined;
              const fallbackModelId = fallbackVal?.[0]?.model_id || policies.find((p) => p.role === role)?.fallbacks?.[0]?.model_id || "";
              const temp = (getEdit(role, "temperature") as number) ?? policies.find((p) => p.role === role)?.temperature ?? 0;
              const heuristic = (getEdit(role, "allow_heuristic") as boolean) ?? policies.find((p) => p.role === role)?.allow_heuristic ?? false;
              const contract = policies.find((p) => p.role === role)?.contract_version || "—";
              const isDirty = !!editing[role];

              return (
                <tr key={role} className={isDirty ? "row-dirty" : ""}>
                  <td className="role-name">{TASK_ROLE_LABELS[role]}</td>
                  <td className="role-desc">{TASK_ROLE_DESCRIPTIONS[role]}</td>
                  <td>
                    <select
                      value={primaryModelId}
                      onChange={(e) => setEdit(role, { primary: { provider_id: "opencode", model_id: e.target.value } })}
                    >
                      {ALLOWED_MODEL_IDS.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={fallbackModelId}
                      onChange={(e) => {
                        const fb = e.target.value ? [{ provider_id: "opencode", model_id: e.target.value }] : [];
                        setEdit(role, { fallbacks: fb });
                      }}
                    >
                      <option value="">—</option>
                      {ALLOWED_MODEL_IDS.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0" max="1" step="0.1"
                      value={temp}
                      onChange={(e) => setEdit(role, { temperature: parseFloat(e.target.value) || 0 })}
                      style={{ width: 55 }}
                    />
                  </td>
                  <td>
                    <select
                      value={heuristic ? "allow" : "deny"}
                      onChange={(e) => setEdit(role, { allow_heuristic: e.target.value === "allow" })}
                    >
                      <option value="deny">deny</option>
                      <option value="allow">allow ⚠</option>
                    </select>
                  </td>
                  <td className="contract-cell">{contract}</td>
                  <td>
                    {isDirty && (
                      <button onClick={() => handleSave(role)} disabled={saving === role}>
                        {saving === role ? "Saving..." : "Save"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
