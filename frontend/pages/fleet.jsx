import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import Layout from '../components/Layout';
import VehicleCard from '../components/VehicleCard';
import { vehicleService } from '../services';
import useStore from '../store/useStore';
import { Search, Filter, RefreshCw, MapPin, Grid, List } from 'lucide-react';
import { toast } from 'sonner';

export default function FleetPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'list'
  const { vehicles, setVehicles } = useStore();

  // Fetch vehicles
  const { data: vehiclesData, isLoading, refetch } = useQuery({
    queryKey: ['vehicles'],
    queryFn: vehicleService.getVehicles,
    refetchInterval: 30000, // Refetch every 30 seconds
    onSuccess: (data) => {
      if (data?.vehicles) {
        setVehicles(data.vehicles);
      }
    },
  });

  // Fetch fleet stats
  const { data: fleetStats, refetch: refetchStats } = useQuery({
    queryKey: ['fleetStats'],
    queryFn: vehicleService.getFleetStats,
    refetchInterval: 30000,
  });

  // Fetch predictions for each vehicle
  const vehicleIds = vehiclesData?.vehicles?.map(v => v.vehicle_id) || [];
  
  const { data: predictionsData } = useQuery({
    queryKey: ['predictions', vehicleIds],
    queryFn: async () => {
      if (vehicleIds.length === 0) return {};
      
      const predictions = {};
      await Promise.all(
        vehicleIds.map(async (vehicleId) => {
          try {
            const pred = await vehicleService.getPredictions(vehicleId);
            predictions[vehicleId] = pred;
          } catch (error) {
            console.error(`Failed to fetch prediction for ${vehicleId}:`, error);
          }
        })
      );
      return predictions;
    },
    enabled: vehicleIds.length > 0,
  });

  // Fetch metrics for each vehicle
  const { data: metricsData } = useQuery({
    queryKey: ['vehicle-metrics', vehicleIds],
    queryFn: async () => {
      if (vehicleIds.length === 0) return {};
      
      const metrics = {};
      await Promise.all(
        vehicleIds.map(async (vehicleId) => {
          try {
            const metric = await vehicleService.getVehicleMetrics(vehicleId);
            metrics[vehicleId] = metric;
          } catch (error) {
            console.error(`Failed to fetch metrics for ${vehicleId}:`, error);
          }
        })
      );
      return metrics;
    },
    enabled: vehicleIds.length > 0,
  });

  const handleRefresh = () => {
    refetch();
    refetchStats();
    toast.success('Fleet data refreshed');
  };

  // Filter vehicles
  const filteredVehicles = (vehiclesData?.vehicles || []).filter((vehicle) => {
    const matchesSearch = vehicle.vehicle_id
      .toLowerCase()
      .includes(searchQuery.toLowerCase());
    
    if (statusFilter === 'all') return matchesSearch;
    
    const prediction = predictionsData?.[vehicle.vehicle_id];
    const status = prediction?.status || 'unknown';
    
    return matchesSearch && status === statusFilter;
  });

  return (
    <Layout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-dark-900">Fleet Management</h1>
            <p className="text-dark-600 mt-1">
              Monitor and manage your entire vehicle fleet
            </p>
          </div>

          <div className="flex items-center space-x-3">
            {/* View Mode Toggle */}
            <div className="flex bg-white border border-dark-200 rounded-lg p-1">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 rounded transition-colors ${
                  viewMode === 'grid'
                    ? 'bg-primary-100 text-primary-600'
                    : 'text-dark-600 hover:bg-dark-50'
                }`}
              >
                <Grid className="w-5 h-5" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded transition-colors ${
                  viewMode === 'list'
                    ? 'bg-primary-100 text-primary-600'
                    : 'text-dark-600 hover:bg-dark-50'
                }`}
              >
                <List className="w-5 h-5" />
              </button>
            </div>

            <motion.button
              onClick={handleRefresh}
              className="px-4 py-2 bg-white border border-dark-200 rounded-lg flex items-center space-x-2 hover:bg-dark-50 transition-colors"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <RefreshCw className="w-4 h-4" />
              <span>Refresh</span>
            </motion.button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            {
              label: 'Total Vehicles',
              value: fleetStats?.total_vehicles || vehiclesData?.count || 0,
              color: 'blue',
              icon: '🚗',
            },
            {
              label: 'Healthy',
              value: fleetStats?.healthy || 0,
              color: 'green',
              icon: '✅',
            },
            {
              label: 'Warning',
              value: fleetStats?.warning || 0,
              color: 'yellow',
              icon: '⚠️',
            },
            {
              label: 'Critical',
              value: fleetStats?.critical || 0,
              color: 'red',
              icon: '🚨',
            },
          ].map((stat, index) => (
            <motion.div
              key={stat.label}
              className="bg-white rounded-xl p-6 shadow-sm border border-dark-200"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-dark-600 text-sm font-medium">
                    {stat.label}
                  </p>
                  <p className="text-3xl font-bold text-dark-900 mt-2">
                    {stat.value}
                  </p>
                </div>
                <div className="text-3xl">
                  {stat.icon}
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-dark-400" />
            <input
              type="text"
              placeholder="Search vehicles..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white border border-dark-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* Status Filter */}
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-dark-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="pl-10 pr-8 py-2 bg-white border border-dark-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 appearance-none cursor-pointer"
            >
              <option value="all">All Status</option>
              <option value="healthy">Healthy</option>
              <option value="warning">Warning</option>
              <option value="critical">Critical</option>
            </select>
          </div>
        </div>

        {/* Vehicle Grid/List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          </div>
        ) : filteredVehicles.length === 0 ? (
          <div className="bg-white rounded-xl p-12 text-center">
            <MapPin className="w-16 h-16 text-dark-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-dark-900 mb-2">
              No Vehicles Found
            </h3>
            <p className="text-dark-600">
              {searchQuery || statusFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'No vehicles in the fleet yet'}
            </p>
          </div>
        ) : (
          <div
            className={
              viewMode === 'grid'
                ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6'
                : 'space-y-4'
            }
          >
            <AnimatePresence>
              {filteredVehicles.map((vehicle, index) => (
                <motion.div
                  key={vehicle.vehicle_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <VehicleCard
                    vehicle={{
                      ...vehicle,
                      ...metricsData?.[vehicle.vehicle_id],
                    }}
                    prediction={predictionsData?.[vehicle.vehicle_id]}
                    onClick={() => {
                      toast.info(`Viewing details for ${vehicle.vehicle_id}`);
                    }}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}

        {/* Summary */}
        {!isLoading && filteredVehicles.length > 0 && (
          <div className="bg-white rounded-xl p-4 border border-dark-200">
            <p className="text-dark-600 text-center">
              Showing <span className="font-semibold">{filteredVehicles.length}</span>{' '}
              of <span className="font-semibold">{vehiclesData?.count || 0}</span>{' '}
              vehicles
              {(searchQuery || statusFilter !== 'all') && (
                <button
                  onClick={() => {
                    setSearchQuery('');
                    setStatusFilter('all');
                  }}
                  className="ml-2 text-primary-600 hover:text-primary-700 font-medium"
                >
                  Clear filters
                </button>
              )}
            </p>
          </div>
        )}
      </div>
    </Layout>
  );
}
