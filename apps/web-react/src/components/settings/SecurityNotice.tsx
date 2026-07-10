export function SecurityNotice() {
  return (
    <div className="security-notice">
      <h3>⚙ Security & Storage</h3>
      <ul>
        <li>
          <strong>Storage:</strong> Session only (lost when browser closes).
          Use "Save to local vault" for persistent encrypted storage.
        </li>
        <li>
          <strong>Local mode:</strong> Using localhost URLs may expose keys to
          other local processes.
        </li>
        <li>
          <strong>Deletion:</strong> Deleting a provider also removes its secret.
          This cannot be undone.
        </li>
        <li>
          <strong>Log protection:</strong> API keys never appear in logs, traces,
          or screenshots.
        </li>
        <li>
          <strong>Model switching:</strong> Changing providers only affects new
          research cases. Completed cases are unaffected.
        </li>
      </ul>
    </div>
  );
}
