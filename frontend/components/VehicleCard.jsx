import { motion } from 'framer-motion';
import { Car, Activity, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { useAnimatedCounter } from '../hooks/useAnimatedCounter';

const statusConfig = {
  healthy: {
    color: 'success',
    icon: CheckCircle,
    label: 'Healthy',
    gradient: 'from-success-500 to-success-600',
  },
  warning: {
    color: 'warning',
    icon: AlertTriangle,
    label: 'Warning',
    gradient: 'from-warning-500 to-warning-600',
  },
  critical: {
    color: 'danger',
    icon: XCircle,
    label: 'Critical',
    gradient: 'from-danger-500 to-danger-600',
  },
  unknown: {
    color: 'dark',
    icon: Activity,
    label: 'Unknown',
    gradient: 'from-dark-400 to-dark-500',
  },
};

export default function VehicleCard({ vehicle, onClick, prediction }) {
  const status = prediction?.prediction || vehicle.status || 'unknown';
  const config = statusConfig[status] || statusConfig.unknown;
  const StatusIcon = config.icon;

  const animatedTemp = useAnimatedCounter(Math.round(vehicle.engine_temp || 0));
  const animatedRpm = useAnimatedCounter(Math.round(vehicle.engine_rpm || 0));

  return (
    <motion.div
      className="card card-hover cursor-pointer overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02, boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)' }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      layout
    >
      {/* Status Bar */}
      <motion.div
        className={`h-2 bg-gradient-to-r ${config.gradient}`}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      />

      {/* Content */}
      <div className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <motion.div
              className={`p-3 rounded-lg bg-${config.color}-50`}
              whileHover={{ rotate: 360 }}
              transition={{ duration: 0.6 }}
            >
              <Car className={`w-6 h-6 text-${config.color}-600`} />
            </motion.div>
            <div>
              <h3 className="text-lg font-semibold text-dark-900">
                {vehicle.vehicle_id}
              </h3>
              <p className="text-sm text-dark-500">{vehicle.model || 'Fleet Vehicle'}</p>
            </div>
          </div>

          <motion.div
            className={`badge badge-${config.color} flex items-center space-x-1`}
            animate={{
              scale: status === 'critical' ? [1, 1.1, 1] : 1,
            }}
            transition={{
              repeat: status === 'critical' ? Infinity : 0,
              duration: 1,
            }}
          >
            <StatusIcon className="w-3 h-3" />
            <span>{config.label}</span>
          </motion.div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <motion.div
            className="bg-dark-50 p-3 rounded-lg"
            whileHover={{ backgroundColor: '#f1f5f9' }}
          >
            <p className="text-xs text-dark-500 mb-1">Engine Temp</p>
            <p className="text-xl font-bold text-dark-900">
              {animatedTemp}°C
            </p>
          </motion.div>

          <motion.div
            className="bg-dark-50 p-3 rounded-lg"
            whileHover={{ backgroundColor: '#f1f5f9' }}
          >
            <p className="text-xs text-dark-500 mb-1">Engine RPM</p>
            <p className="text-xl font-bold text-dark-900">
              {animatedRpm.toLocaleString()}
            </p>
          </motion.div>
        </div>

        {/* Additional Metrics */}
        <div className="flex justify-between text-sm">
          <div>
            <span className="text-dark-500">Speed:</span>
            <span className="ml-1 font-semibold text-dark-900">
              {Math.round(vehicle.speed || 0)} km/h
            </span>
          </div>
          <div>
            <span className="text-dark-500">Fuel:</span>
            <span className="ml-1 font-semibold text-dark-900">
              {Math.round(vehicle.fuel_level || 0)}%
            </span>
          </div>
        </div>

        {/* Prediction Alert */}
        {prediction && prediction.confidence > 0.7 && (
          <motion.div
            className={`mt-4 p-3 rounded-lg bg-${config.color}-50 border border-${config.color}-200`}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            transition={{ duration: 0.3 }}
          >
            <p className="text-xs font-medium text-dark-900 mb-1">
              Prediction: {prediction.prediction.replace('_', ' ').toUpperCase()}
            </p>
            <div className="flex items-center space-x-2">
              <div className="flex-1 bg-dark-200 rounded-full h-2 overflow-hidden">
                <motion.div
                  className={`h-full bg-${config.color}-600`}
                  initial={{ width: 0 }}
                  animate={{ width: `${prediction.confidence * 100}%` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                />
              </div>
              <span className="text-xs font-semibold text-dark-700">
                {Math.round(prediction.confidence * 100)}%
              </span>
            </div>
          </motion.div>
        )}

        {/* Last Update */}
        {vehicle.timestamp && (
          <p className="text-xs text-dark-400 mt-3">
            Last update: {new Date(vehicle.timestamp).toLocaleTimeString()}
          </p>
        )}
      </div>
    </motion.div>
  );
}
