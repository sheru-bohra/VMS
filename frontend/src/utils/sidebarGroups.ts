const STORAGE_PREFIX = 'vms:sidebar-groups:';

export function sidebarGroupsStorageKey(userId: number): string {
  return `${STORAGE_PREFIX}${userId}`;
}

/** @deprecated Use loadOpenGroupId */
export function loadExpandedGroupIds(userId: number): string[] | null {
  const id = loadOpenGroupId(userId);
  return id ? [id] : null;
}

/** @deprecated Use saveOpenGroupId */
export function saveExpandedGroupIds(userId: number, groupIds: string[]): void {
  saveOpenGroupId(userId, groupIds.length > 0 ? groupIds[groupIds.length - 1] : null);
}

/** @deprecated Use buildInitialOpenGroupId */
export function buildInitialExpandedGroups(userId: number, activeGroupId?: string): Set<string> {
  const openId = buildInitialOpenGroupId(userId, activeGroupId);
  return openId ? new Set([openId]) : new Set();
}

export function loadOpenGroupId(userId: number): string | null {
  try {
    const raw = localStorage.getItem(sidebarGroupsStorageKey(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed === 'string') return parsed;
    if (Array.isArray(parsed)) {
      const ids = parsed.filter((id): id is string => typeof id === 'string');
      return ids.length > 0 ? ids[ids.length - 1] : null;
    }
    return null;
  } catch {
    return null;
  }
}

export function saveOpenGroupId(userId: number, groupId: string | null): void {
  try {
    localStorage.setItem(sidebarGroupsStorageKey(userId), JSON.stringify(groupId));
  } catch {
    /* ignore quota / private mode */
  }
}

export function buildInitialOpenGroupId(userId: number, activeGroupId?: string): string | null {
  if (activeGroupId) return activeGroupId;
  return null;
}
