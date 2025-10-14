import { useQuery } from '@tanstack/react-query';
import Layout from '@/components/Layout';
import CAPATable from '@/components/CAPATable';
import { ComponentTrendsChart } from '@/components/AnimatedChart';
import { manufacturingService } from '@/services';
import useStore from '@/store/useStore';

export default function Manufacturing() {
  const { capaFeedback, setCapaFeedback, componentTrends, setComponentTrends } = useStore();

  useQuery({
    queryKey: ['capaFeedback'],
    queryFn: manufacturingService.getCapaFeedback,
    onSuccess: (data) => setCapaFeedback(data.feedback || data),
  });

  useQuery({
    queryKey: ['componentTrends'],
    queryFn: () => manufacturingService.getComponentTrends(null, 30),
    onSuccess: (data) => setComponentTrends(data),
  });

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-dark-900 mb-2">Manufacturing CAPA</h1>
        <p className="text-dark-600">Corrective and Preventive Action insights</p>
      </div>

      <div className="space-y-6">
        {/* Component Trends Chart */}
        {componentTrends && Object.keys(componentTrends).length > 0 && (
          <ComponentTrendsChart data={componentTrends.trends || []} />
        )}

        {/* CAPA Table */}
        <div>
          <h2 className="text-xl font-semibold text-dark-900 mb-4">
            CAPA Reports ({capaFeedback.length})
          </h2>
          <CAPATable
            data={capaFeedback}
            onRowClick={(item) => console.log('CAPA clicked:', item)}
          />
        </div>
      </div>
    </Layout>
  );
}
