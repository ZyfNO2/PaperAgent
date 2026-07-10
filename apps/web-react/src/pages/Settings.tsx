import { useState } from "react";
import { ProviderProfiles } from "../components/settings/ProviderProfiles";
import { ProviderWizard } from "../components/settings/ProviderWizard";
import { RoleRoutingMatrix } from "../components/settings/RoleRoutingMatrix";
import { RunSnapshotViewer } from "../components/settings/RunSnapshotViewer";
import { SecurityNotice } from "../components/settings/SecurityNotice";

type SettingsTab = "providers" | "wizard" | "matrix" | "snapshots";

export default function Settings() {
  const [tab, setTab] = useState<SettingsTab>("providers");
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const tabs: Array<{ key: SettingsTab; label: string }> = [
    { key: "providers", label: "Providers" },
    { key: "wizard", label: "Add Provider" },
    { key: "matrix", label: "Role Matrix" },
    { key: "snapshots", label: "Snapshots" },
  ];

  return (
    <div className="settings-page">
      <div className="settings-header">
        <h2>Settings / Models</h2>
        <div className="settings-tabs">
          {tabs.map((t) => (
            <button
              key={t.key}
              className={`tab-btn ${tab === t.key ? "active" : ""}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="settings-body">
        {tab === "providers" && (
          <ProviderProfiles
            onEdit={() => setTab("wizard")}
            refreshTrigger={refreshTrigger}
          />
        )}
        {tab === "wizard" && <ProviderWizard />}
        {tab === "matrix" && <RoleRoutingMatrix />}
        {tab === "snapshots" && <RunSnapshotViewer />}
      </div>
      <SecurityNotice />
    </div>
  );
}
