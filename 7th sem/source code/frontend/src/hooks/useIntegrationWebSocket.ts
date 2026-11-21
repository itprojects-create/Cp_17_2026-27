import { useEffect, useState, useCallback, useRef } from 'react';
import { wsAuthProtocols } from '../services/api';

const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/^http/, 'ws').replace(/\/$/, '');
const WS_URL = `${BASE_URL}/api/dashboard/ws/integrations`;

export type WSStatus = 'connecting' | 'open' | 'closed' | 'error' | 'polling';

export interface WSMessage {
  type: 'integration_status' | 'sync_started' | 'sync_completed' | 'sync_failed' | 'heartbeat';
  integration_id?: string;
  status?: string;
  lastSync?: string;
  message?: string;
}

export const useIntegrationWebSocket = (onMessage: (data: WSMessage) => void, onReconnect?: () => void) => {
  const [status, setStatus] = useState<WSStatus>('connecting');
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollingInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const onMessageRef = useRef(onMessage);
  const onReconnectRef = useRef(onReconnect);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onReconnectRef.current = onReconnect;
  });

  const token = localStorage.getItem('auth_token');

  const stopHeartbeat = useCallback(() => {
    if (heartbeatInterval.current) {
      clearInterval(heartbeatInterval.current);
      heartbeatInterval.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatInterval.current = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: 'heartbeat' }));
      }
    }, 30000); // 30s heartbeat
  }, [stopHeartbeat]);

  const stopPolling = useCallback(() => {
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
      pollingInterval.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollingInterval.current) return;
    setStatus('polling');
    pollingInterval.current = setInterval(() => {
      onReconnectRef.current?.();
    }, 10000); // Poll every 10s
  }, []);

  // Reconnect timers call through this ref, since `connect` can't reference itself.
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    if (!token) return;
    if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const socket = new WebSocket(WS_URL, wsAuthProtocols(token));
    ws.current = socket;

    socket.onopen = () => {
      setStatus('open');
      stopPolling();
      startHeartbeat();
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
        reconnectTimeout.current = null;
      }
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'heartbeat') return;
        onMessageRef.current(data);
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };

    socket.onclose = (event) => {
      stopHeartbeat();

      if (event.code !== 1000) { // Not a normal closure
        setStatus('connecting');
        if (!reconnectTimeout.current) {
          reconnectTimeout.current = setTimeout(() => {
            reconnectTimeout.current = null;
            connectRef.current();
          }, 5000);
        }
        startPolling();
      } else {
        setStatus('closed');
      }
    };

    socket.onerror = (error) => {
      console.error('Integration WebSocket Error:', error);
      setStatus('error');
      socket.close();
    };
  }, [token, startPolling, startHeartbeat, stopHeartbeat, stopPolling]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (ws.current) {
        // Detach first: closing a socket that is still connecting fires error/close
        // events, which would otherwise schedule a reconnect and start polling after unmount.
        ws.current.onclose = null;
        ws.current.onerror = null;
        ws.current.close(1000);
        ws.current = null;
      }
      stopHeartbeat();
      stopPolling();
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [connect, stopHeartbeat, stopPolling]);

  return { status };
};
