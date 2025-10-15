import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import Layout from '@/components/Layout';
import VehicleCard from '@/components/VehicleCard';
import { TelemetryChart } from '@/components/AnimatedChart';
import { vehicleService } from '@/services';
import useStore from '@/store/useStore';
import { usePolling } from '@/hooks/usePolling';
import { RefreshCw, Search } from 'lucide-react';
import { toast } from 'sonner';

export default function VehicleDashboard() {
  const {
    vehicles,
    setVehicles,
    fleetStats,
    setFleetStats,
    filters,
    updateFilter,
  } = useStore();

  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [vehiclePredictions, setVehiclePredictions] = useState({});

  // Fetch vehicles
  const { data: vehiclesData, refetch: refetchVehicles, isLoading: vehiclesLoading, error: vehiclesError } = useQuery({
    queryKey: ['vehicles'],
    queryFn: vehicleService.getVehicles,
    refetchInterval: 30000,
    staleTime: 0, // Always fetch fresh data
    cacheTime: 0, // Don't cache
  });

  // Update store when vehicles data changes
  useEffect(() => {
    if (vehiclesData) {
      const vehiclesList = vehiclesData.vehicles || vehiclesData;
      console.log('Dashboard: Setting vehicles in store', vehiclesList.length);
      setVehicles(vehiclesList);
    }
  }, [vehiclesData, setVehicles]);

  // Show error toast for vehicles
  useEffect(() => {
    if (vehiclesError) {
      toast.error('Failed to load vehicles');
      console.error(vehiclesError);
    }
  }, [vehiclesError]);

  // Fetch fleet stats
  const { data: fleetStatsData } = useQuery({
    queryKey: ['fleetStats'],
    queryFn: vehicleService.getFleetStats,
    refetchInterval: 30000,
  });

  // Update store when fleet stats data changes
  useEffect(() => {
    if (fleetStatsData) {
      setFleetStats(fleetStatsData);
    }
  }, [fleetStatsData, setFleetStats]);

  // Use vehicles from query data or store
  const activeVehicles = vehiclesData?.vehicles || vehiclesData || vehicles;

  // Fetch predictions for each vehicle
  useEffect(() => {
    const fetchPredictions = async () => {
      for (const vehicle of activeVehicles) {
        try {
          const prediction = await vehicleService.getVehicleStatus(vehicle.vehicle_id);
          setVehiclePredictions((prev) => ({
            ...prev,
            [vehicle.vehicle_id]: prediction,
          }));
        } catch (error) {
          console.error(`Failed to fetch prediction for ${vehicle.vehicle_id}:`, error);
        }
      }
    };

    if (activeVehicles.length > 0) {
      fetchPredictions();
    }
  }, [activeVehicles.length]); // Use length to avoid infinite loop

  // Polling for updates
  usePolling(
    () => {
      refetchVehicles();
    },
    parseInt(process.env.NEXT_PUBLIC_POLLING_INTERVAL) || 10000,
    true
  );

  // Filter vehicles
  const filteredVehicles = activeVehicles.filter((vehicle) => {
    // Check search query match
    const matchesSearch = filters.searchQuery
      ? vehicle.vehicle_id.toLowerCase().includes(filters.searchQuery.toLowerCase())
      : true;

    // Check status filter match - use vehicle.status directly from API
    let matchesStatus = true;
    if (filters.vehicleStatus !== 'all') {
      matchesStatus = vehicle.status === filters.vehicleStatus;
    }

    // Both conditions must be true
    return matchesSearch && matchesStatus;
  });

  console.log('Dashboard: Active vehicles:', activeVehicles.length, 'Filtered:', filteredVehicles.length, 'Filter:', filters.vehicleStatus);

  const handleVehicleClick = (vehicle) => {
    setSelectedVehicle(vehicle);
    toast.info(`Selected vehicle: ${vehicle.vehicle_id}`);
  };

  return (
    <Layout>
      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-500 mb-1">Total Vehicles</p>
              <motion.p
                className="text-3xl font-bold text-dark-900"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', delay: 0.3 }}
              >
                {fleetStats?.total_vehicles || vehicles.length}
              </motion.p>
            </div>
            <div className="p-3 bg-primary-50 rounded-lg">
              <motion.div
                animate={{ scale: [1, 1.1, 1] }}
                transition={{ repeat: Infinity, duration: 2 }}
              >
                🚗
              </motion.div>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-500 mb-1">Healthy</p>
              <p className="text-3xl font-bold text-success-600">
                {fleetStats?.healthy || 0}
              </p>
            </div>
            <div className="p-3 bg-success-50 rounded-lg text-2xl">✅</div>
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-500 mb-1">Warnings</p>
              <p className="text-3xl font-bold text-warning-600">
                {fleetStats?.warning || 0}
              </p>
            </div>
            <div className="p-3 bg-warning-50 rounded-lg text-2xl">⚠️</div>
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-500 mb-1">Critical</p>
              <p className="text-3xl font-bold text-danger-600">
                {fleetStats?.critical || 0}
              </p>
            </div>
            <div className="p-3 bg-danger-50 rounded-lg text-2xl">🚨</div>
          </div>
        </motion.div>
      </div>

      {/* Filters */}
      <div className="flex items-center space-x-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-dark-400" />
          <input
            type="text"
            placeholder="Search vehicles..."
            className="w-full pl-10 pr-4 py-2 border border-dark-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-dark-900 placeholder-dark-400 bg-white"
            value={filters.searchQuery}
            onChange={(e) => updateFilter('searchQuery', e.target.value)}
          />
        </div>

        <select
          className="px-4 py-2 border border-dark-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-dark-900 bg-white"
          value={filters.vehicleStatus}
          onChange={(e) => updateFilter('vehicleStatus', e.target.value)}
        >
          <option value="all">All Status</option>
          <option value="healthy">Healthy</option>
          <option value="warning">Warning</option>
          <option value="critical">Critical</option>
        </select>

        <motion.button
          className="btn-primary flex items-center space-x-2"
          onClick={() => {
            refetchVehicles();
            toast.success('Data refreshed');
          }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh</span>
        </motion.button>
      </div>

      <div className="space-y-6">
        {/* Vehicle Grid */}
        <div>
          <h2 className="text-xl font-semibold text-dark-900 mb-4">
            Fleet Vehicles ({filteredVehicles.length})
          </h2>
            {vehiclesLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="skeleton h-48 rounded-lg" />
                ))}
              </div>
            ) : filteredVehicles.length === 0 ? (
              <div className="card text-center py-12">
                <p className="text-dark-500 text-lg mb-2">No vehicles found</p>
                <p className="text-dark-400 text-sm">
                  {activeVehicles.length === 0 
                    ? 'Loading vehicles...' 
                    : 'Try adjusting your filters'}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {filteredVehicles.map((vehicle, index) => (
                  <VehicleCard
                    key={vehicle.vehicle_id}
                    vehicle={vehicle}
                    prediction={vehiclePredictions[vehicle.vehicle_id]}
                    onClick={() => handleVehicleClick(vehicle)}
                  />
                ))}
              </div>
            )}
          </div>

        {/* Telemetry Chart */}
        {selectedVehicle && (
          <TelemetryChart
            data={selectedVehicle.history || []}
            metrics={['engine_temp', 'vibration', 'engine_rpm']}
          />
        )}
      </div>
    </Layout>
  );
}
