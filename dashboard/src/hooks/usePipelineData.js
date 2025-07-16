import { useEffect, useState } from 'react';

export default function usePipelineData(pipelineId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!pipelineId) return;
    let isMounted = true;
    const API_URL = `http://localhost:8000/pipeline/${pipelineId}/full`;
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(API_URL);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (isMounted) setData(json);
      } catch (err) {
        if (isMounted) setError(err.message);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [pipelineId]);

  return { data, loading, error };
} 