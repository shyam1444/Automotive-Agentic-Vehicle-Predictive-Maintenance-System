import { useEffect, useRef, useState, useCallback } from 'react';
import { io } from 'socket.io-client';
import useStore from '../store/useStore';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

export const useWebSocket = (enabled = true) => {
  const socketRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  const {
    addAlert,
    addSecurityAlert,
    addCapaFeedback,
    setVehicleStatus,
    setWsConnected,
    setLastUpdate,
    addNotification,
  } = useStore();

  const connect = useCallback(() => {
    if (!enabled || socketRef.current?.connected) return;

    try {
      socketRef.current = io(WS_URL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
      });

      socketRef.current.on('connect', () => {
        console.log('✅ WebSocket connected');
        setIsConnected(true);
        setWsConnected(true);
        setError(null);
        addNotification({
          type: 'success',
          message: 'Real-time updates connected',
        });
      });

      socketRef.current.on('disconnect', (reason) => {
        console.log('❌ WebSocket disconnected:', reason);
        setIsConnected(false);
        setWsConnected(false);
        addNotification({
          type: 'warning',
          message: 'Real-time updates disconnected',
        });
      });

      socketRef.current.on('connect_error', (err) => {
        console.error('WebSocket connection error:', err);
        setError(err.message);
        setIsConnected(false);
        setWsConnected(false);
      });

      // Subscribe to vehicle predictions
      socketRef.current.on('vehicle_prediction', (data) => {
        console.log('📊 Vehicle prediction received:', data);
        setVehicleStatus(data.vehicle_id, data);
        setLastUpdate();
        
        if (data.prediction === 'failure_imminent') {
          addNotification({
            type: 'danger',
            message: `Critical: ${data.vehicle_id} failure predicted!`,
          });
        }
      });

      // Subscribe to vehicle alerts
      socketRef.current.on('vehicle_alert', (data) => {
        console.log('🚨 Vehicle alert received:', data);
        addAlert(data);
        setLastUpdate();
        
        if (data.severity === 'critical' || data.severity === 'high') {
          addNotification({
            type: 'danger',
            message: `${data.severity.toUpperCase()}: ${data.message}`,
          });
        }
      });

      // Subscribe to security alerts (UEBA)
      socketRef.current.on('security_alert', (data) => {
        console.log('🔒 Security alert received:', data);
        addSecurityAlert(data);
        setLastUpdate();
        
        if (data.severity === 'critical' || data.severity === 'high') {
          addNotification({
            type: 'danger',
            message: `SECURITY: ${data.description}`,
          });
        }
      });

      // Subscribe to manufacturing feedback
      socketRef.current.on('manufacturing_feedback', (data) => {
        console.log('🏭 Manufacturing feedback received:', data);
        addCapaFeedback(data);
        setLastUpdate();
        
        if (data.priority === 'high') {
          addNotification({
            type: 'warning',
            message: `CAPA: ${data.issue_description}`,
          });
        }
      });

      // Subscribe to maintenance updates
      socketRef.current.on('maintenance_scheduled', (data) => {
        console.log('🔧 Maintenance scheduled:', data);
        setLastUpdate();
        addNotification({
          type: 'info',
          message: `Maintenance scheduled for ${data.vehicle_id}`,
        });
      });

    } catch (err) {
      console.error('Failed to create WebSocket connection:', err);
      setError(err.message);
    }
  }, [enabled, addAlert, addSecurityAlert, addCapaFeedback, setVehicleStatus, setWsConnected, setLastUpdate, addNotification]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
      setWsConnected(false);
    }
  }, [setWsConnected]);

  const emit = useCallback((event, data) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit(event, data);
    }
  }, []);

  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return {
    isConnected,
    error,
    emit,
    connect,
    disconnect,
  };
};

export default useWebSocket;
