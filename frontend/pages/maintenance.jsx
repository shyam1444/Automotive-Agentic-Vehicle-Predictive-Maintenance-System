import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import Layout from '@/components/Layout';
import { maintenanceService } from '@/services';
import useStore from '@/store/useStore';
import { Calendar, Clock, MapPin, CheckCircle, AlertCircle } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';

export default function Maintenance() {
  const { schedules, setSchedules, serviceCenters, setServiceCenters } = useStore();

  useQuery({
    queryKey: ['schedules'],
    queryFn: () => maintenanceService.getSchedules(),
    onSuccess: (data) => setSchedules(data.schedules || data),
  });

  useQuery({
    queryKey: ['serviceCenters'],
    queryFn: maintenanceService.getServiceCenters,
    onSuccess: (data) => setServiceCenters(data),
  });

  const statusConfig = {
    scheduled: { color: 'primary', icon: Calendar, label: 'Scheduled' },
    in_progress: { color: 'warning', icon: Clock, label: 'In Progress' },
    completed: { color: 'success', icon: CheckCircle, label: 'Completed' },
    cancelled: { color: 'danger', icon: AlertCircle, label: 'Cancelled' },
  };

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-dark-900 mb-2">Maintenance Scheduling</h1>
        <p className="text-dark-600">Manage and track vehicle maintenance schedules</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upcoming Maintenance */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-xl font-semibold text-dark-900">Upcoming Maintenance</h2>
          {schedules.map((schedule, index) => {
            const config = statusConfig[schedule.status] || statusConfig.scheduled;
            const Icon = config.icon;

            return (
              <motion.div
                key={schedule.id}
                className="card"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                whileHover={{ scale: 1.02 }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-4 flex-1">
                    <div className={`p-3 rounded-lg bg-${config.color}-50`}>
                      <Icon className={`w-6 h-6 text-${config.color}-600`} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <h3 className="text-lg font-semibold text-dark-900">
                          {schedule.vehicle_id}
                        </h3>
                        <span className={`badge badge-${config.color}`}>
                          {config.label}
                        </span>
                      </div>
                      <p className="text-sm text-dark-600 mb-3">
                        {schedule.service_type || 'Preventive Maintenance'}
                      </p>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="flex items-center space-x-2 text-dark-600">
                          <Calendar className="w-4 h-4" />
                          <span>
                            {schedule.scheduled_date
                              ? format(new Date(schedule.scheduled_date), 'MMM dd, yyyy')
                              : 'TBD'}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2 text-dark-600">
                          <MapPin className="w-4 h-4" />
                          <span>{schedule.service_center || 'Main Service Center'}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}

          {schedules.length === 0 && (
            <motion.div
              className="card text-center py-12"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <CheckCircle className="w-16 h-16 text-success-500 mx-auto mb-4" />
              <p className="text-lg font-medium text-dark-900">No maintenance scheduled</p>
            </motion.div>
          )}
        </div>

        {/* Service Centers */}
        <div>
          <h2 className="text-xl font-semibold text-dark-900 mb-4">Service Centers</h2>
          <div className="space-y-4">
            {(serviceCenters.length > 0 ? serviceCenters : [
              { id: 1, name: 'Main Service Center', available_slots: 5 },
              { id: 2, name: 'North Service Center', available_slots: 3 },
            ]).map((center) => (
              <motion.div
                key={center.id}
                className="card"
                whileHover={{ scale: 1.02 }}
              >
                <h3 className="font-semibold text-dark-900 mb-2">{center.name}</h3>
                <p className="text-sm text-dark-600">
                  Available slots: {center.available_slots || 0}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
}
