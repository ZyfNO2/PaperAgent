import { useState } from "react";
import {
  validateProvider,
  discoverModels,
  probeModel,
} from "../../lib/providersApi";
import { ALLOWED_MODEL_IDS, TASK_ROLE_LABELS, WIZARD_STEPS } from "../../types/providers";
import type { TaskRole, ProviderWizardState, ModelInfo } from "../../types/providers";

export function ProviderWizard() {
  const [state, setState] = useState<ProviderWizardState>({
    step: 1,
    label: "",
    protocol: "openai_compatible",
    base_url: "",
    discover_result: "idle",
    discovered_models: [],
    manual_model_id: "",
    selected_models: [],
    probe_status: {},
    role_bindings: Object.fromEntries(
      (Object.keys(TASK_ROLE_LABELS) as TaskRole[]).map((r) => [
        r,
        { primary_model: "", fallback_model: "", temperature: 0.0 },
      ])
    ) as ProviderWizardState["role_bindings"],
    saving: false,
    error: null,
  });

  const set = (patch: Partial<ProviderWizardState>) =>
    setState((s) => ({ ...s, ...patch }));

  const nextStep = () => set({ step: state.step + 1, error: null });
  const prevStep = () => set({ step: Math.max(1, state.step - 1), error: null });

  const handleValidate = async () => {
    set({ error: null });
    try {
      const result = await validateProvider({ base_url: state.base_url, api_key: "" });
      if (!result.valid) {
        set({ error: result.message || `Validation failed: ${result.error_type}` });
        return;
      }
      nextStep();
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : "Validation failed" });
    }
  };

  const handleDiscover = async () => {
    set({ discover_result: "loading", error: null });
    try {
      const result = await discoverModels("temp");
      if (result.source === "auto") {
        const models: ModelInfo[] = result.models.map((m) => ({
          model_id: m.model_id,
          label: m.label,
          discovery_source: "auto" as const,
          probed_capabilities: null,
        }));
        set({ discover_result: "auto", discovered_models: models });
      } else {
        set({ discover_result: "manual" });
      }
      nextStep();
    } catch {
      set({ discover_result: "manual", error: "Auto-discovery unavailable" });
      nextStep();
    }
  };

  const handleProbe = async () => {
    const models = state.selected_models.length > 0
      ? state.discovered_models.filter((m) => state.selected_models.includes(m.model_id))
      : state.discovered_models;

    const newProbe: Record<string, Record<string, string>> = {};
    for (const m of models) {
      newProbe[m.model_id] = { chat: "probing", json_object: "probing", json_schema: "probing", reasoning_envelope: "probing", streaming: "probing" };
    }
    set({ probe_status: newProbe as ProviderWizardState["probe_status"] });

    for (const m of models) {
      try {
        const caps = await probeModel("temp", m.model_id);
        newProbe[m.model_id] = {
          chat: caps.chat ? "pass" : "fail",
          json_object: caps.json_object ? "pass" : "fail",
          json_schema: caps.json_schema ? "pass" : "fail",
          reasoning_envelope: caps.reasoning_envelope ? "pass" : "fail",
          streaming: caps.streaming ? "pass" : "fail",
        };
      } catch {
        newProbe[m.model_id] = { chat: "fail", json_object: "fail", json_schema: "fail", reasoning_envelope: "fail", streaming: "fail" };
      }
      set({ probe_status: { ...newProbe } as ProviderWizardState["probe_status"] });
    }
  };

  const probeIcon = (s: string) => {
    switch (s) {
      case "pass": return "✅";
      case "fail": return "❌";
      case "probing": return "⏳";
      default: return "—";
    }
  };

  return (
    <div className="provider-wizard">
      <h3>Add Provider Wizard</h3>

      {/* Step indicators */}
      <div className="wizard-steps">
        {WIZARD_STEPS.map((s) => (
          <span key={s.step} className={`wizard-step ${state.step >= s.step ? "active" : ""} ${state.step === s.step ? "current" : ""}`}>
            {s.step}. {s.label}
          </span>
        ))}
      </div>

      {state.error && <div className="settings-error">{state.error}</div>}

      {/* Step 1: Basic info */}
      {state.step === 1 && (
        <div className="wizard-body">
          <label>Label: <input value={state.label} onChange={(e) => set({ label: e.target.value })} placeholder="My Provider" /></label>
          <label>Protocol:
            <select value={state.protocol} onChange={(e) => set({ protocol: e.target.value as "openai_compatible" | "anthropic_like" })}>
              <option value="openai_compatible">OpenAI Compatible</option>
              <option value="anthropic_like">Anthropic-like</option>
            </select>
          </label>
          <div className="wizard-actions">
            <button onClick={nextStep} disabled={!state.label.trim()}>Next</button>
          </div>
        </div>
      )}

      {/* Step 2: Connection */}
      {state.step === 2 && (
        <div className="wizard-body">
          <label>Base URL: <input value={state.base_url} onChange={(e) => set({ base_url: e.target.value })} placeholder="https://api.example.com" /></label>
          <label>API Key: <input type="password" onChange={(e) => {
            // Key is sent but never stored in React state
            e.target.value = "";
          }} placeholder="Enter API key (will not be echoed)" /></label>
          <div className="wizard-actions">
            <button onClick={prevStep}>Back</button>
            <button onClick={handleValidate} disabled={!state.base_url.trim()}>Validate</button>
          </div>
        </div>
      )}

      {/* Step 3: Validate */}
      {state.step === 3 && (
        <div className="wizard-body">
          <p>Connection validated. Click next to discover models.</p>
          <div className="wizard-actions">
            <button onClick={prevStep}>Back</button>
            <button onClick={handleDiscover}>Discover Models</button>
          </div>
        </div>
      )}

      {/* Step 4: Model Discovery */}
      {state.step === 4 && (
        <div className="wizard-body">
          {state.discover_result === "loading" && <p>Discovering models...</p>}
          {state.discover_result === "auto" && (
            <div>
              <p>Discovered {state.discovered_models.length} models:</p>
              {state.discovered_models.map((m) => (
                <label key={m.model_id} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={state.selected_models.includes(m.model_id)}
                    onChange={(e) => {
                      const sel = e.target.checked
                        ? [...state.selected_models, m.model_id]
                        : state.selected_models.filter((x) => x !== m.model_id);
                      set({ selected_models: sel });
                    }}
                  />
                  {m.model_id} {m.label ? `(${m.label})` : ""}
                </label>
              ))}
            </div>
          )}
          {state.discover_result === "manual" && (
            <div>
              <p>Auto-discovery not supported. Enter model ID manually:</p>
              <label>Model ID: <input value={state.manual_model_id} onChange={(e) => set({ manual_model_id: e.target.value })} placeholder="model-id" /></label>
            </div>
          )}
          <div className="wizard-actions">
            <button onClick={prevStep}>Back</button>
            <button onClick={handleProbe}>Probe Capabilities</button>
          </div>
        </div>
      )}

      {/* Step 5: Capability Probe */}
      {state.step === 5 && (
        <div className="wizard-body">
          <h4>Capability Probe Results</h4>
          {Object.keys(state.probe_status).length === 0 && <p>Run probes first.</p>}
          {Object.entries(state.probe_status).map(([modelId, caps]) => (
            <div key={modelId} className="probe-model">
              <strong>{modelId}</strong>
              <div className="probe-grid">
                {Object.entries(caps as Record<string, string>).map(([cap, status]) => (
                  <span key={cap} className={`probe-cap probe-${status}`}>
                    {cap}: {probeIcon(status)}
                  </span>
                ))}
              </div>
            </div>
          ))}
          <div className="wizard-actions">
            <button onClick={prevStep}>Back</button>
            <button onClick={nextStep}>Next: Role Binding</button>
          </div>
        </div>
      )}

      {/* Step 6: Role Binding */}
      {state.step === 6 && (
        <div className="wizard-body">
          <h4>Role Routing</h4>
          {(Object.keys(state.role_bindings) as TaskRole[]).map((role) => (
            <div key={role} className="role-binding-row">
              <span className="role-label">{TASK_ROLE_LABELS[role]}</span>
              <span className="role-id">{role}</span>
              <select
                value={state.role_bindings[role].primary_model}
                onChange={(e) => set({
                  role_bindings: {
                    ...state.role_bindings,
                    [role]: { ...state.role_bindings[role], primary_model: e.target.value },
                  },
                })}
              >
                <option value="">-- Primary --</option>
                {ALLOWED_MODEL_IDS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <select
                value={state.role_bindings[role].fallback_model}
                onChange={(e) => set({
                  role_bindings: {
                    ...state.role_bindings,
                    [role]: { ...state.role_bindings[role], fallback_model: e.target.value },
                  },
                })}
              >
                <option value="">-- Fallback (optional) --</option>
                {ALLOWED_MODEL_IDS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <input
                type="number"
                min="0"
                max="1"
                step="0.1"
                value={state.role_bindings[role].temperature}
                onChange={(e) => set({
                  role_bindings: {
                    ...state.role_bindings,
                    [role]: { ...state.role_bindings[role], temperature: parseFloat(e.target.value) || 0 },
                  },
                })}
                style={{ width: 60 }}
              />
            </div>
          ))}
          <div className="wizard-actions">
            <button onClick={prevStep}>Back</button>
            <button onClick={nextStep}>Save</button>
          </div>
        </div>
      )}

      {/* Step 7: Save */}
      {state.step === 7 && (
        <div className="wizard-body">
          <h4>Review & Save</h4>
          <p>Label: {state.label}</p>
          <p>Protocol: {state.protocol}</p>
          <p>Base URL: {state.base_url}</p>
          <p>Models: {state.selected_models.length || (state.manual_model_id ? 1 : 0)}</p>
          <p>Storage: Session only (lost on browser close)</p>
          <div className="wizard-actions">
            <button onClick={prevStep}>Back</button>
            <button onClick={() => { set({ saving: true, error: null }); }} disabled={state.saving}>
              {state.saving ? "Saving..." : "Save (Session Only)"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
