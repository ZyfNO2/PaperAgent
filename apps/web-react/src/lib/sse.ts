import type { SSEEvent, SSEEventType } from '../types/api';

const EVENT_TYPES: SSEEventType[] = [
  'search_started', 'node_current', 'papers_update', 'papers_verified',
  'adapter_result', 'adapter_status', 'search_completed', 'filter_result',
  'verify_completed', 'candidate_count', 'expansion_started', 'expansion_completed',
  'repos_update', 'datasets_update', 'node_complete', 'done', 'error',
];

export function connectSSE(
  caseId: string,
  handlers: {
    onEvent: (event: SSEEvent) => void;
    onError?: () => void;
  },
): () => void {
  const source = new EventSource(`/api/v1/research/${caseId}/stream`);

  const cleanups: (() => void)[] = [];

  for (const type of EVENT_TYPES) {
    const listener = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        handlers.onEvent({ type, data });
      } catch {
        // ignore parse errors
      }
    };
    source.addEventListener(type, listener);
    cleanups.push(() => source.removeEventListener(type, listener));
  }

  source.onerror = () => {
    handlers.onError?.();
    source.close();
  };

  return () => {
    cleanups.forEach((fn) => fn());
    source.close();
  };
}
