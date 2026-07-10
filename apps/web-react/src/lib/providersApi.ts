import type {
  ProviderListResponse,
  PolicyListResponse,
  SnapshotListResponse,
  ProviderProfile,
  ModelPolicyItem,
} from "../types/providers";

const BASE_URL = "/api/v1";
const PROVIDERS_BASE = `${BASE_URL}/providers`;
const LLM_BASE = `${BASE_URL}/llm`;

export async function listProviders(): Promise<ProviderListResponse> {
  const resp = await fetch(PROVIDERS_BASE + "/");
  if (!resp.ok) throw new Error(`Provider list failed: ${resp.status}`);
  return resp.json();
}

export async function getProvider(providerId: string): Promise<ProviderProfile> {
  const resp = await fetch(`${PROVIDERS_BASE}/${providerId}`);
  if (!resp.ok) throw new Error(`Provider get failed: ${resp.status}`);
  return resp.json();
}

export async function createProvider(data: {
  label: string;
  protocol: string;
  base_url: string;
  api_key?: string;
}): Promise<ProviderProfile> {
  const resp = await fetch(PROVIDERS_BASE + "/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Provider create failed: ${resp.status}`);
  }
  return resp.json();
}

export async function deleteProvider(providerId: string): Promise<void> {
  const resp = await fetch(`${PROVIDERS_BASE}/${providerId}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(`Provider delete failed: ${resp.status}`);
}

export async function validateProvider(data: {
  base_url: string;
  api_key: string;
}): Promise<{ valid: boolean; error_type?: string; message?: string }> {
  const resp = await fetch(`${PROVIDERS_BASE}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return resp.json();
}

export async function discoverModels(providerId: string): Promise<{
  models: Array<{ model_id: string; label: string | null }>;
  source: "auto" | "unsupported";
}> {
  const resp = await fetch(`${PROVIDERS_BASE}/${providerId}/discover`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error(`Model discovery failed: ${resp.status}`);
  return resp.json();
}

export async function probeModel(
  providerId: string,
  modelId: string
): Promise<{
  chat: boolean;
  json_object: boolean;
  json_schema: boolean;
  reasoning_envelope: boolean;
  streaming: boolean;
}> {
  const resp = await fetch(
    `${PROVIDERS_BASE}/${providerId}/models/${modelId}/probe`,
    { method: "POST" }
  );
  if (!resp.ok) throw new Error(`Model probe failed: ${resp.status}`);
  return resp.json();
}

export async function listPolicies(): Promise<PolicyListResponse> {
  const resp = await fetch(`${LLM_BASE}/policies`);
  if (!resp.ok) throw new Error(`Policy list failed: ${resp.status}`);
  return resp.json();
}

export async function updatePolicy(policy: ModelPolicyItem): Promise<ModelPolicyItem> {
  const resp = await fetch(`${LLM_BASE}/policies`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policy),
  });
  if (!resp.ok) throw new Error(`Policy update failed: ${resp.status}`);
  return resp.json();
}

export async function listSnapshots(
  caseId: string
): Promise<SnapshotListResponse> {
  const resp = await fetch(
    `${BASE_URL}/research/${caseId}/snapshots`
  );
  if (!resp.ok) throw new Error(`Snapshot list failed: ${resp.status}`);
  return resp.json();
}
