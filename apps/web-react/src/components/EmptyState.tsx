interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon = '📭', title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <div className="empty-title">{title}</div>
      {description && <div className="empty-desc">{description}</div>}
      {action && (
        <button className="btn-primary" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}
