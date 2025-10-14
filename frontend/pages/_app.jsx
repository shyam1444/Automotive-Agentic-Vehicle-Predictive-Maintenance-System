import '@/styles/globals.css';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { Toaster } from 'sonner';
import useWebSocket from '@/hooks/useWebSocket';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5000,
    },
  },
});

export default function App({ Component, pageProps }) {
  const [mounted, setMounted] = useState(false);
  
  // Enable WebSocket for real-time updates
  const wsEnabled = process.env.NEXT_PUBLIC_ENABLE_WEBSOCKET === 'true';
  useWebSocket(wsEnabled);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <Component {...pageProps} />
      <Toaster position="top-right" richColors />
    </QueryClientProvider>
  );
}
