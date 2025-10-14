import { useQuery } from '@tanstack/react-query';
import Layout from '@/components/Layout';
import { AlertDistributionChart, ComponentTrendsChart } from '@/components/AnimatedChart';
import { analyticsService } from '@/services';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';

export default function Analytics() {
  const { data: overview } = useQuery({
    queryKey: ['dashboardOverview'],
    queryFn: analyticsService.getDashboardOverview,
  });

  const { data: metrics } = useQuery({
    queryKey: ['aggregatedMetrics'],
    queryFn: () => analyticsService.getAggregatedMetrics('24h'),
  });

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-dark-900 mb-2">Analytics Dashboard</h1>
        <p className="text-dark-600">Comprehensive system insights and trends</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
        {[
          { label: 'Total Predictions', value: overview?.total_predictions || 0, icon: Activity, color: 'primary' },
          { label: 'Avg Accuracy', value: `${((overview?.avg_accuracy || 0) * 100).toFixed(1)}%`, icon: TrendingUp, color: 'success' },
          { label: 'Anomalies Detected', value: overview?.anomalies || 0, icon: TrendingDown, color: 'warning' },
          { label: 'CAPA Reports', value: overview?.capa_count || 0, icon: Activity, color: 'danger' },
        ].map((metric, index) => {
          const Icon = metric.icon;
          return (
            <motion.div
              key={metric.label}
              className="card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-500 mb-1">{metric.label}</p>
                  <p className={`text-3xl font-bold text-${metric.color}-600`}>
                    {metric.value}
                  </p>
                </div>
                <div className={`p-3 bg-${metric.color}-50 rounded-lg`}>
                  <Icon className={`w-6 h-6 text-${metric.color}-600`} />
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AlertDistributionChart
          data={[
            { severity: 'Low', count: 45 },
            { severity: 'Medium', count: 32 },
            { severity: 'High', count: 18 },
            { severity: 'Critical', count: 5 },
          ]}
        />
        <ComponentTrendsChart
          data={metrics?.component_trends || []}
        />
      </div>
    </Layout>
  );
}
