import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Layout from '@/components/Layout';
import CAPATable from '@/components/CAPATable';
import { ComponentTrendsChart } from '@/components/AnimatedChart';
import { manufacturingService } from '@/services';
import useStore from '@/store/useStore';

export default function Manufacturing() {
  const { capaFeedback, setCapaFeedback, componentTrends, setComponentTrends } = useStore();

  // Fixed React Query v5 compatibility - removed deprecated onSuccess
  const { data: capaFeedbackData } = useQuery({
    queryKey: ['capaFeedback'],
    queryFn: manufacturingService.getCapaFeedback,
    refetchInterval: 30000,
    staleTime: 0,
  });

  const { data: componentTrendsData } = useQuery({
    queryKey: ['componentTrends'],
    queryFn: () => manufacturingService.getComponentTrends(null, 30),
    refetchInterval: 30000,
    staleTime: 0,
  });

  // Update store when data changes
  useEffect(() => {
    if (capaFeedbackData) {
      const feedbackList = capaFeedbackData.feedback || capaFeedbackData;
      console.log('Manufacturing: Setting CAPA feedback in store', feedbackList.length);
      setCapaFeedback(feedbackList);
    }
  }, [capaFeedbackData, setCapaFeedback]);

  useEffect(() => {
    if (componentTrendsData) {
      const trendsList = componentTrendsData.trends || componentTrendsData;
      console.log('Manufacturing: Setting component trends in store', trendsList.length);
      setComponentTrends(trendsList);
    }
  }, [componentTrendsData, setComponentTrends]);

  // Use direct data with store fallback for immediate display
  const activeCapa = capaFeedbackData?.feedback || capaFeedbackData || capaFeedback;
  const activeTrends = componentTrendsData?.trends || componentTrendsData || componentTrends;

  console.log('Manufacturing: activeTrends', activeTrends);
  console.log('Manufacturing: componentTrendsData', componentTrendsData);

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-dark-900 mb-2">Manufacturing CAPA</h1>
        <p className="text-dark-600">Corrective and Preventive Action insights</p>
      </div>

      <div className="space-y-6">
        {/* Component Trends Chart */}
        {activeTrends && Array.isArray(activeTrends) && activeTrends.length > 0 && (
          <ComponentTrendsChart data={activeTrends} />
        )}

        {/* CAPA Table */}
        <div>
          <h2 className="text-xl font-semibold text-dark-900 mb-4">
            CAPA Reports ({activeCapa.length})
          </h2>
          <CAPATable
            data={activeCapa}
            onRowClick={(item) => console.log('CAPA clicked:', item)}
          />
        </div>
      </div>
    </Layout>
  );
}
