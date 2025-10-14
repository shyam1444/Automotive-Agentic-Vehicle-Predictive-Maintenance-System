import apiClient from './api';

// Vehicle Services
export const vehicleService = {
  // Get all vehicles
  getVehicles: async () => {
    const response = await apiClient.get('/fleet/vehicles');
    return response.data;
  },

  // Get vehicle by ID
  getVehicle: async (vehicleId) => {
    const response = await apiClient.get(`/fleet/vehicle/${vehicleId}`);
    return response.data;
  },

  // Get vehicle status (Phase 3 - Predictions)
  getVehicleStatus: async (vehicleId) => {
    const response = await apiClient.get(`/vehicle/${vehicleId}/status`);
    return response.data;
  },

  // Get vehicle telemetry history
  getVehicleTelemetry: async (vehicleId, hours = 24) => {
    const response = await apiClient.get(`/fleet/vehicle/${vehicleId}/telemetry`, {
      params: { hours },
    });
    return response.data;
  },

  // Get fleet statistics
  getFleetStats: async () => {
    const response = await apiClient.get('/fleet/stats');
    return response.data;
  },

  // Get vehicle predictions
  getPredictions: async (vehicleId) => {
    const response = await apiClient.get(`/predictions/${vehicleId}`);
    return response.data;
  },

  // Get vehicle metrics
  getVehicleMetrics: async (vehicleId) => {
    const response = await apiClient.get(`/vehicle/${vehicleId}/metrics`);
    return response.data;
  },
};

// Alert Services
export const alertService = {
  // Get all alerts
  getAlerts: async (params = {}) => {
    const response = await apiClient.get('/alerts', { params });
    return response.data;
  },

  // Get alerts for specific vehicle
  getVehicleAlerts: async (vehicleId, severity = null) => {
    const response = await apiClient.get(`/alerts/${vehicleId}`, {
      params: { severity },
    });
    return response.data;
  },

  // Acknowledge alert
  acknowledgeAlert: async (alertId) => {
    const response = await apiClient.post(`/alerts/${alertId}/acknowledge`);
    return response.data;
  },

  // Get alert statistics
  getAlertStats: async () => {
    const response = await apiClient.get('/alerts/stats');
    return response.data;
  },
};

// Maintenance Services (Phase 4)
export const maintenanceService = {
  // Get all maintenance schedules
  getSchedules: async (params = {}) => {
    const response = await apiClient.get('/schedules', { params });
    return response.data;
  },

  // Get vehicle maintenance schedule
  getVehicleSchedule: async (vehicleId) => {
    const response = await apiClient.get(`/schedules/${vehicleId}`);
    return response.data;
  },

  // Book maintenance slot
  bookMaintenance: async (data) => {
    const response = await apiClient.post('/schedules', data);
    return response.data;
  },

  // Update maintenance status
  updateMaintenanceStatus: async (scheduleId, status) => {
    const response = await apiClient.put(`/schedules/${scheduleId}`, { status });
    return response.data;
  },

  // Get available service centers
  getServiceCenters: async () => {
    const response = await apiClient.get('/service-centers');
    return response.data;
  },

  // Get maintenance recommendations
  getRecommendations: async (vehicleId) => {
    const response = await apiClient.get(`/maintenance/recommendations/${vehicleId}`);
    return response.data;
  },
};

// Manufacturing Services (Phase 5)
export const manufacturingService = {
  // Get CAPA feedback
  getCapaFeedback: async (params = {}) => {
    const response = await apiClient.get('/manufacturing/feedback', { params });
    return response.data;
  },

  // Get component failure trends
  getComponentTrends: async (component = null, days = 30) => {
    const response = await apiClient.get('/manufacturing/trends', {
      params: { component, days },
    });
    return response.data;
  },

  // Submit CAPA report
  submitCapaReport: async (data) => {
    const response = await apiClient.post('/manufacturing/capa', data);
    return response.data;
  },

  // Get manufacturing insights
  getInsights: async () => {
    const response = await apiClient.get('/manufacturing/insights');
    return response.data;
  },

  // Get component failure statistics
  getComponentStats: async () => {
    const response = await apiClient.get('/manufacturing/component-stats');
    return response.data;
  },
};

// Security Services (Phase 6 - UEBA)
export const securityService = {
  // Get security alerts
  getSecurityAlerts: async (params = {}) => {
    const response = await apiClient.get('/ueba/alerts', { params });
    return response.data;
  },

  // Get specific alert
  getAlert: async (alertId) => {
    const response = await apiClient.get(`/ueba/alerts/${alertId}`);
    return response.data;
  },

  // Update alert status
  updateAlertStatus: async (alertId, status) => {
    const response = await apiClient.put(`/ueba/alerts/${alertId}/status`, { status });
    return response.data;
  },

  // Get monitored agents
  getAgents: async () => {
    const response = await apiClient.get('/ueba/agents');
    return response.data;
  },

  // Get agent metrics
  getAgentMetrics: async (agentId) => {
    const response = await apiClient.get(`/ueba/agents/${agentId}/metrics`);
    return response.data;
  },

  // Get agent alerts
  getAgentAlerts: async (agentId) => {
    const response = await apiClient.get(`/ueba/agents/${agentId}/alerts`);
    return response.data;
  },

  // Get UEBA statistics
  getUebaStats: async () => {
    const response = await apiClient.get('/ueba/stats');
    return response.data;
  },

  // Get severity trends
  getSeverityTrends: async (days = 7) => {
    const response = await apiClient.get('/ueba/trends/severity', {
      params: { days },
    });
    return response.data;
  },

  // ElasticSearch search
  searchActivity: async (query) => {
    const response = await apiClient.get('/ueba/elasticsearch/search', {
      params: { query_string: query },
    });
    return response.data;
  },
};

// Analytics Services
export const analyticsService = {
  // Get dashboard overview
  getDashboardOverview: async () => {
    const response = await apiClient.get('/analytics/overview');
    return response.data;
  },

  // Get aggregated metrics
  getAggregatedMetrics: async (timeRange = '24h') => {
    const response = await apiClient.get('/analytics/metrics', {
      params: { time_range: timeRange },
    });
    return response.data;
  },

  // Get component failure analysis
  getFailureAnalysis: async (days = 30) => {
    const response = await apiClient.get('/analytics/failure-analysis', {
      params: { days },
    });
    return response.data;
  },

  // Get predictive insights
  getPredictiveInsights: async () => {
    const response = await apiClient.get('/analytics/predictive-insights');
    return response.data;
  },
};

// Health check
export const healthCheck = async () => {
  try {
    const response = await apiClient.get('/health');
    return response.data;
  } catch (error) {
    return { status: 'error', message: error.message };
  }
};

export default {
  vehicleService,
  alertService,
  maintenanceService,
  manufacturingService,
  securityService,
  analyticsService,
  healthCheck,
};
