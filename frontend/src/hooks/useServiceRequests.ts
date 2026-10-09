import { useState, useEffect, useCallback } from 'react';
import {
  getDashboardStats,
  updateServiceRequestStatus,
  updateMaintenanceStatus,
  updateComplaintStatus,
  type DashboardStats,
} from '../api/client';

// ─── useServiceRequests Hook ──────────────────────────────────────────────────

export function useServiceRequests(pollIntervalMs = 10000) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      const data = await getDashboardStats();
      setStats(data);
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    const interval = setInterval(fetch, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetch, pollIntervalMs]);

  const updateStatus = useCallback(async (id: string, status: string, type: string) => {
    try {
      if (type === 'MAINTENANCE') {
        await updateMaintenanceStatus(id, status);
      } else if (type === 'COMPLAINT') {
        await updateComplaintStatus(id, status);
      } else {
        await updateServiceRequestStatus(id, status);
      }
      await fetch();
    } catch {
      // Silently ignore — dashboard will show next poll
    }
  }, [fetch]);

  return { stats, loading, error, refresh: fetch, updateStatus };
}
