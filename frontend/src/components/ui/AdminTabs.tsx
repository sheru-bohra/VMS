export interface AdminTabItem {
  id: string;
  label: string;
  count?: number;
}

interface AdminTabsProps {
  tabs: AdminTabItem[];
  active: string;
  onChange: (id: string) => void;
  ariaLabel?: string;
}

export function AdminTabs({ tabs, active, onChange, ariaLabel = 'Sections' }: AdminTabsProps) {
  return (
    <div className="vms-tab-bar" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`vms-tab ${isActive ? 'vms-tab--active' : ''}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
            {tab.count != null && <span className="vms-tab__count">({tab.count})</span>}
          </button>
        );
      })}
    </div>
  );
}
