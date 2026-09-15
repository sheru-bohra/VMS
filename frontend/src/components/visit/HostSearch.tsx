import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { PublicHost } from '../../types';

interface HostSearchProps {
  siteToken: string;
  value: PublicHost | null;
  onChange: (host: PublicHost | null) => void;
  error?: string;
}

export function HostSearch({ siteToken, value, onChange, error }: HostSearchProps) {
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<PublicHost[]>([]);
  const [loading, setLoading] = useState(false);

  const doSearch = useCallback(async (term: string) => {
    setLoading(true);
    try {
      const hosts = await api.publicHosts(siteToken, term);
      setResults(hosts);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [siteToken]);

  useEffect(() => {
    if (value) return;
    const timer = setTimeout(() => doSearch(search), 250);
    return () => clearTimeout(timer);
  }, [search, value, doSearch]);

  if (value) {
    return (
      <div>
        <div className="reg-host-selected">
          <span>
            {value.name}
            {value.department ? ` · ${value.department}` : ''}
          </span>
          <button type="button" onClick={() => { onChange(null); setSearch(''); }}>Change</button>
        </div>
        {error && <p className="reg-form-error">{error}</p>}
      </div>
    );
  }

  return (
    <div className="reg-host-search">
      <input
        type="search"
        className={`reg-form-input ${error ? 'reg-form-input--error' : ''}`}
        placeholder="Search host by name…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        aria-label="Search host"
        autoComplete="off"
      />
      {loading && <p className="reg-form-error" style={{ color: 'var(--color-slate-500)' }}>Searching…</p>}
      {results.length > 0 && (
        <ul className="reg-host-results" role="listbox">
          {results.map((host) => (
            <li key={host.id}>
              <button type="button" onClick={() => { onChange(host); setResults([]); }}>
                {host.name}
                {host.department ? <span style={{ color: 'var(--color-slate-500)' }}> · {host.department}</span> : null}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="reg-form-error">{error}</p>}
    </div>
  );
}
