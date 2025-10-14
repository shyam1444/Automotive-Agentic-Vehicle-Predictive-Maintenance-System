import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, X, CheckCircle, Info, XCircle } from 'lucide-react';
import { format } from 'date-fns';
import { forwardRef } from 'react';

const severityConfig = {
  low: {
    icon: Info,
    color: 'primary',
    bg: 'bg-primary-50',
    border: 'border-primary-200',
    text: 'text-primary-800',
  },
  medium: {
    icon: AlertTriangle,
    color: 'warning',
    bg: 'bg-warning-50',
    border: 'border-warning-200',
    text: 'text-warning-800',
  },
  high: {
    icon: AlertTriangle,
    color: 'danger',
    bg: 'bg-danger-50',
    border: 'border-danger-200',
    text: 'text-danger-800',
  },
  critical: {
    icon: XCircle,
    color: 'danger',
    bg: 'bg-danger-100',
    border: 'border-danger-300',
    text: 'text-danger-900',
  },
};

const AlertCard = forwardRef(function AlertCard({ alert, onDismiss, onAcknowledge, index = 0 }, ref) {
  const config = severityConfig[alert.severity] || severityConfig.medium;
  const Icon = config.icon;

  return (
    <motion.div
      ref={ref}
      className={`${config.bg} border-l-4 ${config.border} p-4 rounded-lg shadow-md overflow-hidden`}
      initial={{ opacity: 0, x: 100, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: -100, scale: 0.9 }}
      transition={{
        type: 'spring',
        stiffness: 500,
        damping: 30,
        delay: index * 0.05,
      }}
      whileHover={{ scale: 1.02, boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)' }}
      layout
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3 flex-1">
          {/* Icon with pulse animation for critical */}
          <motion.div
            className={`p-2 rounded-full ${config.bg}`}
            animate={
              alert.severity === 'critical'
                ? {
                    scale: [1, 1.2, 1],
                    boxShadow: [
                      '0 0 0 0 rgba(239, 68, 68, 0.4)',
                      '0 0 0 10px rgba(239, 68, 68, 0)',
                    ],
                  }
                : {}
            }
            transition={{
              repeat: alert.severity === 'critical' ? Infinity : 0,
              duration: 2,
            }}
          >
            <Icon className={`w-5 h-5 ${config.text}`} />
          </motion.div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2 mb-1">
              <motion.span
                className={`badge badge-${config.color} text-xs font-semibold uppercase`}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2 }}
              >
                {alert.severity}
              </motion.span>
              <span className="text-sm font-medium text-dark-900">
                {alert.vehicle_id || 'System'}
              </span>
            </div>

            <motion.p
              className="text-sm text-dark-800 mb-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
            >
              {alert.message || alert.description}
            </motion.p>

            {/* Metrics if available */}
            {alert.field && alert.value !== undefined && (
              <motion.div
                className="text-xs text-dark-600 space-y-1"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                transition={{ delay: 0.4 }}
              >
                <div>
                  <span className="font-medium">Field:</span> {alert.field}
                </div>
                <div>
                  <span className="font-medium">Value:</span> {alert.value}
                  {alert.threshold && (
                    <span className="ml-2 text-dark-500">
                      (Threshold: {JSON.stringify(alert.threshold)})
                    </span>
                  )}
                </div>
              </motion.div>
            )}

            {/* Timestamp */}
            <motion.p
              className="text-xs text-dark-500 mt-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
            >
              {alert.timestamp
                ? format(new Date(alert.timestamp), 'MMM dd, yyyy HH:mm:ss')
                : 'Just now'}
            </motion.p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2 ml-4">
          {onAcknowledge && alert.status !== 'acknowledged' && (
            <motion.button
              className="p-1 rounded hover:bg-success-100 text-success-600 transition-colors"
              onClick={() => onAcknowledge(alert)}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              title="Acknowledge"
            >
              <CheckCircle className="w-5 h-5" />
            </motion.button>
          )}

          {onDismiss && (
            <motion.button
              className="p-1 rounded hover:bg-dark-200 text-dark-600 transition-colors"
              onClick={() => onDismiss(alert)}
              whileHover={{ scale: 1.1, rotate: 90 }}
              whileTap={{ scale: 0.9 }}
              title="Dismiss"
            >
              <X className="w-5 h-5" />
            </motion.button>
          )}
        </div>
      </div>
    </motion.div>
  );
});

export default AlertCard;

// Alert List Component with AnimatePresence
export function AlertList({ alerts, onDismiss, onAcknowledge, maxDisplay = 10 }) {
  const displayAlerts = alerts.slice(0, maxDisplay);

  return (
    <div className="space-y-3">
      <AnimatePresence mode="popLayout">
        {displayAlerts.map((alert, index) => (
          <AlertCard
            key={alert.id || alert.alert_id || index}
            alert={alert}
            onDismiss={onDismiss}
            onAcknowledge={onAcknowledge}
            index={index}
          />
        ))}
      </AnimatePresence>

      {alerts.length > maxDisplay && (
        <motion.p
          className="text-sm text-dark-500 text-center py-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          +{alerts.length - maxDisplay} more alerts
        </motion.p>
      )}

      {alerts.length === 0 && (
        <motion.div
          className="text-center py-12"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <CheckCircle className="w-16 h-16 text-success-500 mx-auto mb-4" />
          <p className="text-lg font-medium text-dark-900 mb-1">All Clear!</p>
          <p className="text-sm text-dark-500">No active alerts at this time</p>
        </motion.div>
      )}
    </div>
  );
}
