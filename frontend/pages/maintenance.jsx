import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import Layout from '@/components/Layout';
import { maintenanceService } from '@/services';
import useStore from '@/store/useStore';
import { Calendar, Clock, MapPin, CheckCircle, AlertCircle, Filter, Play, Check, X } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';

export default function Maintenance() {
  const { schedules, setSchedules, serviceCenters, setServiceCenters } = useStore();
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterSeverity, setFilterSeverity] = useState('all');

  // Fetch schedules
  const { data: schedulesData } = useQuery({
    queryKey: ['schedules'],
    queryFn: () => maintenanceService.getSchedules(),
    refetchInterval: 30000,
  });

  // Fetch service centers
  const { data: serviceCentersData } = useQuery({
    queryKey: ['serviceCenters'],
    queryFn: maintenanceService.getServiceCenters,
    refetchInterval: 60000,
  });

  // Update store when schedules data changes
  useEffect(() => {
    if (schedulesData) {
      const schedulesList = schedulesData.schedules || schedulesData;
      console.log('Maintenance: Setting schedules in store', schedulesList.length);
      setSchedules(schedulesList);
    }
  }, [schedulesData, setSchedules]);

  // Update store when service centers data changes
  useEffect(() => {
    if (serviceCentersData) {
      setServiceCenters(serviceCentersData);
    }
  }, [serviceCentersData, setServiceCenters]);

  const statusConfig = {
    pending: { color: 'warning', icon: Clock, label: 'Pending', bgColor: 'bg-warning-50', textColor: 'text-warning-600', iconBg: 'bg-warning-50', iconColor: 'text-warning-600' },
    scheduled: { color: 'primary', icon: Calendar, label: 'Scheduled', bgColor: 'bg-primary-50', textColor: 'text-primary-600', iconBg: 'bg-primary-50', iconColor: 'text-primary-600' },
    in_progress: { color: 'primary', icon: Play, label: 'In Progress', bgColor: 'bg-blue-50', textColor: 'text-blue-600', iconBg: 'bg-blue-50', iconColor: 'text-blue-600' },
    completed: { color: 'success', icon: CheckCircle, label: 'Completed', bgColor: 'bg-success-50', textColor: 'text-success-600', iconBg: 'bg-success-50', iconColor: 'text-success-600' },
    cancelled: { color: 'danger', icon: X, label: 'Cancelled', bgColor: 'bg-danger-50', textColor: 'text-danger-600', iconBg: 'bg-danger-50', iconColor: 'text-danger-600' },
  };

  // Use schedules from query data or store
  const activeSchedules = schedulesData?.schedules || schedulesData || schedules;

  const handleStatusChange = async (schedule, newStatus) => {
    try {
      // Call API to update status
      await maintenanceService.updateMaintenanceStatus(schedule.schedule_id, newStatus);
      
      // Optimistically update local state
      const updatedSchedules = activeSchedules.map(s => 
        s.schedule_id === schedule.schedule_id ? { ...s, status: newStatus } : s
      );
      setSchedules(updatedSchedules);
      
      toast.success(`Schedule ${schedule.schedule_id} marked as ${newStatus}`);
    } catch (error) {
      console.error('Error updating schedule status:', error);
      toast.error('Failed to update schedule status');
    }
  };

  // Filter schedules
  const filteredSchedules = activeSchedules.filter(schedule => {
    const matchesStatus = filterStatus === 'all' || schedule.status === filterStatus;
    const matchesSeverity = filterSeverity === 'all' || schedule.severity === filterSeverity;
    return matchesStatus && matchesSeverity;
  });

  console.log('Maintenance: Active schedules:', activeSchedules.length, 'Filtered:', filteredSchedules.length);

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-dark-900 mb-2">Maintenance Scheduling</h1>
        <p className="text-dark-600">Manage and track vehicle maintenance schedules</p>
      </div>

      {/* Help Banner */}
      {activeSchedules.filter(s => s.status === 'pending').length > 0 && (
        <motion.div 
          className="bg-warning-50 border-l-4 border-warning-500 p-4 mb-6 rounded-r-lg"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-warning-600 mt-0.5 mr-3 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-semibold text-warning-900 mb-1">
                {activeSchedules.filter(s => s.status === 'pending').length} Maintenance Schedule(s) Awaiting Approval
              </h3>
              <p className="text-sm text-warning-800">
                Review pending schedules below and click <strong>"Approve"</strong> to schedule maintenance, 
                or <strong>"Cancel"</strong> to dismiss. Approved schedules can then be progressed through 
                "Start Work" → "Complete".
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
        <div className="card">
          <p className="text-sm text-dark-500 mb-1">Total Schedules</p>
          <p className="text-3xl font-bold text-dark-900">{activeSchedules.length}</p>
        </div>
        <div className="card">
          <p className="text-sm text-dark-500 mb-1">Pending</p>
          <p className="text-3xl font-bold text-warning-600">
            {activeSchedules.filter(s => s.status === 'pending').length}
          </p>
        </div>
        <div className="card">
          <p className="text-sm text-dark-500 mb-1">In Progress</p>
          <p className="text-3xl font-bold text-blue-600">
            {activeSchedules.filter(s => s.status === 'in_progress').length}
          </p>
        </div>
        <div className="card">
          <p className="text-sm text-dark-500 mb-1">Completed</p>
          <p className="text-3xl font-bold text-success-600">
            {activeSchedules.filter(s => s.status === 'completed').length}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center space-x-4 mb-6">
        <div className="flex items-center space-x-2">
          <Filter className="w-5 h-5 text-dark-500" />
          <span className="text-sm font-medium text-dark-700">Filters:</span>
        </div>
        <select
          className="px-4 py-2 border border-dark-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-dark-900 bg-white"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        >
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="scheduled">Scheduled</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
        </select>
        <select
          className="px-4 py-2 border border-dark-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-dark-900 bg-white"
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
        >
          <option value="all">All Severity</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
        </select>
        <div className="text-sm text-dark-600">
          Showing {filteredSchedules.length} of {activeSchedules.length} schedules
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upcoming Maintenance */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-xl font-semibold text-dark-900">Maintenance Schedules</h2>
          {filteredSchedules.map((schedule, index) => {
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
                    <div className={`p-3 rounded-lg ${config.iconBg}`}>
                      <Icon className={`w-6 h-6 ${config.iconColor}`} />
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
                      <div className="grid grid-cols-2 gap-4 text-sm mb-3">
                        <div className="flex items-center space-x-2 text-dark-600">
                          <Calendar className="w-4 h-4" />
                          <span>
                            {schedule.scheduled_date
                              ? format(new Date(schedule.scheduled_date), 'MMM dd, yyyy HH:mm')
                              : 'TBD'}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2 text-dark-600">
                          <MapPin className="w-4 h-4" />
                          <span>{schedule.service_center || 'Main Service Center'}</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center space-x-4">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            schedule.severity === 'critical' ? 'bg-danger-100 text-danger-700' :
                            schedule.severity === 'high' ? 'bg-warning-100 text-warning-700' :
                            'bg-primary-100 text-primary-700'
                          }`}>
                            {schedule.severity?.toUpperCase()}
                          </span>
                          <span className="text-dark-600">
                            {schedule.estimated_duration} • ${schedule.estimated_cost}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Action Buttons */}
                  <div className="flex items-center space-x-2 mt-4 pt-4 border-t border-dark-100">
                    {schedule.status === 'pending' && (
                      <>
                        <button
                          onClick={() => handleStatusChange(schedule, 'scheduled')}
                          className="btn-sm btn-primary flex items-center space-x-1"
                        >
                          <CheckCircle className="w-4 h-4" />
                          <span>Approve</span>
                        </button>
                        <button
                          onClick={() => handleStatusChange(schedule, 'cancelled')}
                          className="btn-sm btn-outline-danger flex items-center space-x-1"
                        >
                          <X className="w-4 h-4" />
                          <span>Cancel</span>
                        </button>
                      </>
                    )}
                    {schedule.status === 'scheduled' && (
                      <button
                        onClick={() => handleStatusChange(schedule, 'in_progress')}
                        className="btn-sm btn-success flex items-center space-x-1"
                      >
                        <Play className="w-4 h-4" />
                        <span>Start Work</span>
                      </button>
                    )}
                    {schedule.status === 'in_progress' && (
                      <button
                        onClick={() => handleStatusChange(schedule, 'completed')}
                        className="btn-sm btn-success flex items-center space-x-1"
                      >
                        <Check className="w-4 h-4" />
                        <span>Complete</span>
                      </button>
                    )}
                    {schedule.status === 'completed' && (
                      <span className="text-sm text-success-600 font-medium flex items-center space-x-1">
                        <CheckCircle className="w-4 h-4" />
                        <span>Work Completed</span>
                      </span>
                    )}
                    {schedule.status === 'cancelled' && (
                      <span className="text-sm text-danger-600 font-medium flex items-center space-x-1">
                        <X className="w-4 h-4" />
                        <span>Cancelled</span>
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}

          {filteredSchedules.length === 0 && activeSchedules.length > 0 && (
            <motion.div
              className="card text-center py-12"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <Filter className="w-16 h-16 text-dark-300 mx-auto mb-4" />
              <p className="text-lg font-medium text-dark-900">No schedules match your filters</p>
              <p className="text-sm text-dark-600 mt-2">Try adjusting your filter settings</p>
            </motion.div>
          )}
          
          {activeSchedules.length === 0 && (
            <motion.div
              className="card text-center py-12"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <CheckCircle className="w-16 h-16 text-success-500 mx-auto mb-4" />
              <p className="text-lg font-medium text-dark-900">No maintenance scheduled</p>
              <p className="text-sm text-dark-600 mt-2">All vehicles are in good condition</p>
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
