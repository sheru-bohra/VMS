import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../services/api';
import type { PublicHost } from '../../types';

interface StaffHostSearchProps {
  locationId: number | '';
  value: number | '';
  onSelect: (host: PublicHost | null) => void;
  disabled?: boolean;
}

export function StaffHostSearch({ locationId, value, onSelect, disabled }: StaffHostSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PublicHost[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!locationId) {
      setResults([]);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      api.locationHosts(Number(locationId), query.trim() || undefined)
        .then((hosts) => setResults(hosts))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [locationId, query]);

  const selectHost = useCallback(
    (host: PublicHost) => {
      onSelect(host);
      setQuery(host.name);
      setOpen(false);
    },
    [onSelect],
  );

  return (
    <div className="rv-host-search">
      <input
        type="text"
        className="reg-form-input"
        placeholder="Search by name or department…"
        value={query}
        disabled={disabled || !locationId}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          if (!e.target.value) onSelect(null);
        }}
        onFocus={() => setOpen(true)}
        aria-autocomplete="list"
        aria-expanded={open}
      />
      {open && locationId && (results.length > 0 || loading) && (
        <ul className="rv-host-search__list" role="listbox">
          {loading && <li className="rv-host-search__item rv-host-search__item--muted">Searching…</li>}
          {!loading &&
            results.map((host) => (
              <li key={host.id}>
                <button
                  type="button"
                  className={`rv-host-search__item ${value === host.id ? 'rv-host-search__item--active' : ''}`}
                  onClick={() => selectHost(host)}
                >
                  <span className="rv-host-search__name">{host.name}</span>
                  {host.department && <span className="rv-host-search__dept">{host.department}</span>}
                  {host.email && <span className="rv-host-search__email">{host.email}</span>}
                </button>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
