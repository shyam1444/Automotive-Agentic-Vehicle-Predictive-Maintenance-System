import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

const useStore = create(
  devtools((set, get) => ({
    // Vehicle State
    vehicles: [],
    selectedVehicle: null,
    vehicleStatus: {},
    vehicleTelemetry: {},
    fleetStats: null,
    
    setVehicles: (vehicles) => set({ vehicles }),
    setSelectedVehicle: (vehicle) => set({ selectedVehicle: vehicle }),
    setVehicleStatus: (vehicleId, status) =>
      set((state) => ({
        vehicleStatus: { ...state.vehicleStatus, [vehicleId]: status },
      })),
    setVehicleTelemetry: (vehicleId, telemetry) =>
      set((state) => ({
        vehicleTelemetry: { ...state.vehicleTelemetry, [vehicleId]: telemetry },
      })),
    setFleetStats: (stats) => set({ fleetStats: stats }),

    // Alert State
    alerts: [],
    activeAlerts: [],
    alertStats: null,
    
    setAlerts: (alerts) => set({ alerts }),
    addAlert: (alert) =>
      set((state) => ({
        alerts: [alert, ...state.alerts],
        activeAlerts: alert.status === 'active' 
          ? [alert, ...state.activeAlerts] 
          : state.activeAlerts,
      })),
    updateAlert: (alertId, updates) =>
      set((state) => ({
        alerts: state.alerts.map((a) =>
          a.id === alertId ? { ...a, ...updates } : a
        ),
        activeAlerts: state.activeAlerts.map((a) =>
          a.id === alertId ? { ...a, ...updates } : a
        ),
      })),
    setAlertStats: (stats) => set({ alertStats: stats }),
    setActiveAlerts: (alerts) => set({ activeAlerts: alerts }),

    // Maintenance State
    schedules: [],
    upcomingMaintenance: [],
    serviceCenters: [],
    
    setSchedules: (schedules) => set({ schedules }),
    setUpcomingMaintenance: (maintenance) => set({ upcomingMaintenance: maintenance }),
    setServiceCenters: (centers) => set({ serviceCenters: centers }),
    addSchedule: (schedule) =>
      set((state) => ({
        schedules: [schedule, ...state.schedules],
      })),
    updateSchedule: (scheduleId, updates) =>
      set((state) => ({
        schedules: state.schedules.map((s) =>
          s.id === scheduleId ? { ...s, ...updates } : s
        ),
      })),

    // Manufacturing State (CAPA)
    capaFeedback: [],
    componentTrends: {},
    manufacturingInsights: null,
    
    setCapaFeedback: (feedback) => set({ capaFeedback: feedback }),
    addCapaFeedback: (feedback) =>
      set((state) => ({
        capaFeedback: [feedback, ...state.capaFeedback],
      })),
    setComponentTrends: (trends) => set({ componentTrends: trends }),
    setManufacturingInsights: (insights) => set({ manufacturingInsights: insights }),

    // Security State (UEBA)
    securityAlerts: [],
    agents: [],
    uebaStats: null,
    severityTrends: [],
    
    setSecurityAlerts: (alerts) => set({ securityAlerts: alerts }),
    addSecurityAlert: (alert) =>
      set((state) => ({
        securityAlerts: [alert, ...state.securityAlerts],
      })),
    updateSecurityAlert: (alertId, updates) =>
      set((state) => ({
        securityAlerts: state.securityAlerts.map((a) =>
          a.alert_id === alertId ? { ...a, ...updates } : a
        ),
      })),
    setAgents: (agents) => set({ agents }),
    setUebaStats: (stats) => set({ uebaStats: stats }),
    setSeverityTrends: (trends) => set({ severityTrends: trends }),

    // Analytics State
    dashboardOverview: null,
    aggregatedMetrics: null,
    failureAnalysis: null,
    
    setDashboardOverview: (overview) => set({ dashboardOverview: overview }),
    setAggregatedMetrics: (metrics) => set({ aggregatedMetrics: metrics }),
    setFailureAnalysis: (analysis) => set({ failureAnalysis: analysis }),

    // UI State
    sidebarOpen: true,
    activeTab: 'overview',
    loading: false,
    error: null,
    notifications: [],
    
    toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    setActiveTab: (tab) => set({ activeTab: tab }),
    setLoading: (loading) => set({ loading }),
    setError: (error) => set({ error }),
    addNotification: (notification) =>
      set((state) => ({
        notifications: [...state.notifications, { ...notification, id: Date.now() }],
      })),
    removeNotification: (id) =>
      set((state) => ({
        notifications: state.notifications.filter((n) => n.id !== id),
      })),
    clearNotifications: () => set({ notifications: [] }),

    // WebSocket State
    wsConnected: false,
    lastUpdate: null,
    
    setWsConnected: (connected) => set({ wsConnected: connected }),
    setLastUpdate: () => set({ lastUpdate: new Date().toISOString() }),

    // Filters
    filters: {
      vehicleStatus: 'all', // all, healthy, warning, critical
      alertSeverity: 'all', // all, low, medium, high, critical
      timeRange: '24h', // 1h, 6h, 24h, 7d, 30d
      searchQuery: '',
    },
    
    updateFilter: (key, value) =>
      set((state) => ({
        filters: { ...state.filters, [key]: value },
      })),
    resetFilters: () =>
      set({
        filters: {
          vehicleStatus: 'all',
          alertSeverity: 'all',
          timeRange: '24h',
          searchQuery: '',
        },
      }),

    // Reset entire store
    reset: () => set({
      vehicles: [],
      selectedVehicle: null,
      vehicleStatus: {},
      alerts: [],
      schedules: [],
      capaFeedback: [],
      securityAlerts: [],
      agents: [],
      loading: false,
      error: null,
    }),
  }))
);

export default useStore;
