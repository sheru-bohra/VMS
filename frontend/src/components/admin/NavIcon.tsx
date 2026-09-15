import type { NavIconName, NavIconTone } from '../../utils/navigationConfig';

const PATHS: Record<NavIconName, string> = {
  'layout-dashboard': 'M3 3h8v8H3zm10 0h8v5h-8zm0 7h8v8h-8zM3 13h8v8H3z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm8 2a3 3 0 1 0 0-6M22 21v-2a4 4 0 0 0-3-3.87',
  clock: 'M12 6v6l4 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  'user-check': 'M16 21v-2a4 4 0 0 0-3-3.87M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm6 2l2 2 4-4',
  mail: 'M4 4h16v16H4zm0 0 16 10L4 4',
  'clipboard-list': 'M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2M9 12h6M9 16h6',
  'qr-code': 'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm4 4h1m6-11v3m0 4v3m-3-3h3',
  'check-circle': 'M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4 12 14.01l-3-3',
  'shield-alert': 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10M12 8v4m0 4h.01',
  'shield-check': 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10m-2.5-7.5L9 12l2 2 4-4',
  'triangle-alert': 'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4m0 4h.01',
  'key-round': 'M2 18v3h3l11-11-3-3zm12-8 3 3M15 6l3 3',
  'building-2': 'M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2M10 6h4M10 10h4M10 14h4M10 18h4',
  'bar-chart': 'M12 20V10M18 20V4M6 20v-4',
  sparkles: 'M12 2l1.2 3.6L15.8 7l-3.6 1.2L12 12l-1.2-3.6L7.2 7l3.6-1.2zM5 18l.6 1.8L7.4 20l-1.8.6L5 22.4l-.6-1.8L2.8 20l1.8-.6zM19 16l.6 1.8L21.4 18l-1.8.6L19 20.4l-.6-1.8L16.8 18l1.8-.6z',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a7.4 7.4 0 0 0 .1-1 7.4 7.4 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a7.6 7.6 0 0 0-1.7-1l-.4-2.6h-4l-.4 2.6a7.6 7.6 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0-.1 1 7.4 7.4 0 0 0 .1 1l-2 1.6 2 3.4 2.4-1a7.6 7.6 0 0 0 1.7 1l.4 2.6h4l.4-2.6a7.6 7.6 0 0 0 1.7-1l2.4 1 2-3.4z',
  'map-pin': 'M12 21s7-4.5 7-10a7 7 0 1 0-14 0c0 5.5 7 10 7 10zm0-8a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  lock: 'M7 11V7a5 5 0 0 1 10 0v4M5 11h14v10H5z',
  badge: 'M12 2l3 2 3.5-.5.5 3.5 2.5 2.5-2.5 2.5-.5 3.5L15 20l-3-2-3 2 3.5-.5.5-3.5-2.5-2.5 2.5-2.5-.5-3.5L9 4l3-2z',
  activity: 'M22 12h-4l-3 9L9 3l-3 9H2',
  'users-round': 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm11 4a3 3 0 1 0 0-6',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  briefcase: 'M9 6V4a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v2M4 10h20v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm4 0V8h8v2',
  'chart-line': 'M3 3v18h18M7 14l4-4 3 3 5-6',
  sliders: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M2 14h4M10 8h4M18 16h4',
  'user-round-plus': 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm11 2v6m3-3h-6M19 8v6m3-3h-6',
};

interface NavIconProps {
  name: NavIconName;
  tone?: NavIconTone;
  active?: boolean;
  className?: string;
}

export function NavIcon({ name, tone, active, className = '' }: NavIconProps) {
  const d = PATHS[name];
  const toneClass = tone ? `nav-icon--tone-${tone}` : '';
  const activeClass = active ? 'nav-icon--active' : '';

  return (
    <span className={`nav-icon ${toneClass} ${activeClass} ${className}`.trim()} aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d={d} />
      </svg>
    </span>
  );
}
