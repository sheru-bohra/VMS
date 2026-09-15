import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../services/api';
import type { AIInsightItem, CopilotResponse } from '../../types';
import { LoadingState, ErrorState } from '../../components/StatePanels';
import { useOperationalLocations } from '../../hooks/useOperationalLocations';
import { useAuth } from '../../hooks/useAuth';
import { hasPermission } from '../../utils/permissions';
import '../../styles/admin-pages.css';

type Tab = 'copilot' | 'insights';

export function VmsCopilotPage() {
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];
  const locations = useOperationalLocations(user);
  const canManage = hasPermission(permissions, 'ai.management.read');
  const canDismiss = hasPermission(permissions, 'ai.insights.dismiss');

  const [tab, setTab] = useState<Tab>('copilot');
  const [locationId, setLocationId] = useState<number | undefined>();
  const [question, setQuestion] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [response, setResponse] = useState<CopilotResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insights, setInsights] = useState<AIInsightItem[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [priorityFilter, setPriorityFilter] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    api.copilotSuggestions().then((r) => setSuggestions(r.suggestions)).catch(() => {});
  }, []);

  const loadInsights = useCallback(async () => {
    setInsightsLoading(true);
    try {
      const res = await api.aiInsights({
        location_id: locationId,
        priority: priorityFilter || undefined,
        status: 'ACTIVE',
      });
      setInsights(res.items);
    } catch {
      setInsights([]);
    } finally {
      setInsightsLoading(false);
    }
  }, [locationId, priorityFilter]);

  useEffect(() => {
    if (tab === 'insights') loadInsights();
  }, [tab, loadInsights]);

  const ask = async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.copilotQuery({ question: q, location_id: locationId });
      setResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Copilot request failed');
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = () => {
    const q = question.trim();
    if (!q) return;
    ask(q);
  };

  const refreshInsights = async () => {
    setRefreshing(true);
    try {
      await api.aiInsightsRefresh(locationId);
      await loadInsights();
    } finally {
      setRefreshing(false);
    }
  };

  const dismiss = async (id: number) => {
    await api.aiInsightDismiss(id);
    setInsights((prev) => prev.filter((i) => i.id !== id));
  };

  return (
    <div className="vms-page-shell">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>VMS Copilot</h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)', margin: '0.25rem 0 0' }}>
            AI-generated operational assistance. Verify important decisions in VMS.
          </p>
        </div>
        {locations.length > 0 && (
          <select value={locationId ?? ''} onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : undefined)}>
            <option value="">{canManage ? 'All Locations' : 'All assigned locations'}</option>
            {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        )}
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button type="button" className={tab === 'copilot' ? 'admin-btn admin-btn--primary' : 'admin-btn'} onClick={() => setTab('copilot')}>Copilot</button>
        <button type="button" className={tab === 'insights' ? 'admin-btn admin-btn--primary' : 'admin-btn'} onClick={() => setTab('insights')}>Insights</button>
      </div>

      {tab === 'copilot' && (
        <div>
          <p style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>Ask about visitor operations</p>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What needs attention right now?"
              style={{ flex: 1, padding: '0.5rem' }}
              maxLength={1000}
            />
            <button type="button" className="admin-btn admin-btn--primary" disabled={loading} onClick={onSubmit}>
              {loading ? 'Thinking…' : 'Ask'}
            </button>
          </div>

          {suggestions.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <p style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)', marginBottom: '0.35rem' }}>Suggested questions</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                {suggestions.map((s) => (
                  <button key={s} type="button" className="admin-btn" style={{ fontSize: '0.8125rem' }} onClick={() => { setQuestion(s); ask(s); }}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && <p style={{ color: 'var(--color-danger)', fontSize: '0.875rem' }}>{error}</p>}

          {loading && <LoadingState message="Preparing response…" />}

          {response && !loading && (
            <div style={{ border: '1px solid var(--color-slate-200)', borderRadius: '6px', padding: '1rem' }}>
              {response.response.denied && (
                <p style={{ color: 'var(--color-danger)', fontWeight: 600, marginBottom: '0.5rem' }}>
                  This information is outside your VMS access scope.
                </p>
              )}
              {response.response.unavailable && (
                <p style={{ color: 'var(--color-slate-600)', marginBottom: '0.5rem' }}>
                  AI assistance is temporarily unavailable. Visitor operations remain unaffected.
                </p>
              )}
              <p style={{ fontSize: '0.9375rem', marginBottom: '0.75rem' }}>{response.response.answer}</p>

              {response.response.insights?.length > 0 && (
                <div style={{ marginBottom: '0.75rem' }}>
                  {response.response.insights.map((ins, idx) => (
                    <div key={idx} style={{ marginBottom: '0.5rem', fontSize: '0.8125rem' }}>
                      <strong>{ins.title}</strong> — {ins.explanation}
                    </div>
                  ))}
                </div>
              )}

              {response.response.recommended_actions?.length > 0 && (
                <div style={{ marginBottom: '0.75rem' }}>
                  {response.response.recommended_actions.map((a) => (
                    <Link key={a.path} to={a.path} className="admin-btn" style={{ marginRight: '0.35rem', fontSize: '0.8125rem' }}>
                      {a.label}
                    </Link>
                  ))}
                </div>
              )}

              {response.response.source_references?.length > 0 && (
                <div style={{ fontSize: '0.8125rem', color: 'var(--color-slate-500)' }}>
                  <strong>Sources</strong>
                  <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
                    {response.response.source_references.map((s, i) => (
                      <li key={i}>
                        {s.path ? <Link to={s.path}>{s.label}</Link> : s.label}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === 'insights' && (
        <div>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
              <option value="">All priorities</option>
              <option value="URGENT">URGENT</option>
              <option value="ATTENTION">ATTENTION</option>
              <option value="INFORMATION">INFORMATION</option>
            </select>
            <button type="button" className="admin-btn" disabled={refreshing} onClick={refreshInsights}>
              {refreshing ? 'Refreshing…' : 'Refresh Insights'}
            </button>
          </div>

          {insightsLoading ? <LoadingState message="Loading insights…" /> : (
            insights.length === 0 ? (
              <p style={{ fontSize: '0.875rem', color: 'var(--color-slate-500)' }}>No active insights for current filters.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {insights.map((ins) => (
                  <div key={ins.id} style={{ border: '1px solid var(--color-slate-200)', borderRadius: '6px', padding: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: ins.priority === 'URGENT' ? 'var(--color-danger)' : 'var(--color-slate-600)' }}>
                        {ins.priority}
                      </span>
                      {canDismiss && (
                        <button type="button" className="admin-btn" style={{ fontSize: '0.75rem' }} onClick={() => dismiss(ins.id)}>Dismiss</button>
                      )}
                    </div>
                    <h3 style={{ fontSize: '0.9375rem', margin: '0.25rem 0' }}>{ins.title}</h3>
                    <p style={{ fontSize: '0.8125rem', margin: '0 0 0.5rem' }}>{ins.summary}</p>
                    {ins.location_name && <p style={{ fontSize: '0.75rem', color: 'var(--color-slate-500)' }}>{ins.location_name}</p>}
                    {ins.evidence?.bullets && (
                      <ul style={{ fontSize: '0.8125rem', margin: '0.5rem 0 0', paddingLeft: '1.25rem' }}>
                        {ins.evidence.bullets.map((b, i) => <li key={i}>{b}</li>)}
                      </ul>
                    )}
                    {ins.deep_link && (
                      <Link to={ins.deep_link} style={{ fontSize: '0.8125rem' }}>View in VMS →</Link>
                    )}
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
