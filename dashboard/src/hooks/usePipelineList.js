import { useEffect, useState } from 'react';

const API_URL = 'http://localhost:8000/pipelines';

export default function usePipelineList() {
  const [pipelines, setPipelines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchList() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(API_URL);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (isMounted && json.pipelines) {
          const arr = Object.entries(json.pipelines).map(([id, status]) => ({ id, status }));
          setPipelines(arr);
        }
      } catch (err) {
        if (isMounted) setError(err.message);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    fetchList();
    const interval = setInterval(fetchList, 5000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return { pipelines, loading, error };
} 