import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import Layout from '@/components/Layout';
import { AlertList } from '@/components/AlertCard';
import { securityService } from '@/services';
import useStore from '@/store/useStore';
import { Shield, Activity, AlertTriangle } from 'lucide-react';

export default function Security() {
  const { securityAlerts, setSecurityAlerts, uebaStats, setUebaStats, agents, setAgents } = useStore();

  useQuery({
    queryKey: ['securityAlerts'],
    queryFn: securityService.getSecurityAlerts,
    onSuccess: (data) => setSecurityAlerts(data.alerts || data),
  });

  useQuery({
    queryKey: ['uebaStats'],
    queryFn: securityService.getUebaStats,
    onSuccess: (data) => setUebaStats(data),
  });

  useQuery({
    queryKey: ['agents'],
    queryFn: securityService.getAgents,
    onSuccess: (data) => setAgents(data.agents || data),
  });

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-dark-900 mb-2">Security & UEBA</h1>
        <p className="text-dark-600">User and Entity Behavior Analytics</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-500 mb-1">Monitored Agents</p>
              <p className="text-3xl font-bold text-dark-900">
                {uebaStats?.agents_monitored || agents.length}
              </p>
            </div>
            <div className="p-3 bg-primary-50 rounded-lg">
              <Activity className="w-6 h-6 text-primary-600" />
            </div>
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-500 mb-1">Security Alerts</p>
              <p className="text-3xl font-bold text-danger-600">
                {securityAlerts.length}
              </p>
            </div>
            <div className="p-3 bg-danger-50 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-danger-600" />
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
              <p className="text-sm text-dark-500 mb-1">Status</p>
              <p className="text-xl font-bold text-success-600">Active</p>
            </div>
            <div className="p-3 bg-success-50 rounded-lg">
              <Shield className="w-6 h-6 text-success-600" />
            </div>
          </div>
        </motion.div>
      </div>

      {/* Security Alerts */}
      <div>
        <h2 className="text-xl font-semibold text-dark-900 mb-4">
          Security Alerts ({securityAlerts.length})
        </h2>
        <AlertList alerts={securityAlerts} maxDisplay={50} />
      </div>
    </Layout>
  );
}
