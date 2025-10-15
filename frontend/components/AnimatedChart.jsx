import { motion } from 'framer-motion';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const chartVariants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: {
      duration: 0.5,
      ease: 'easeOut',
    },
  },
};

export default function AnimatedChart({
  data,
  type = 'line',
  title,
  dataKeys = [],
  height = 300,
  colors = ['#0ea5e9', '#22c55e', '#f59e0b', '#ef4444'],
  xAxisKey = 'timestamp',
  showLegend = true,
  showGrid = true,
}) {
  const renderChart = () => {
    const commonProps = {
      data,
      margin: { top: 5, right: 30, left: 20, bottom: 5 },
    };

    const tooltipStyle = {
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      border: '1px solid #e2e8f0',
      borderRadius: '8px',
      padding: '8px',
    };

    switch (type) {
      case 'line':
        return (
          <LineChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />}
            <XAxis
              dataKey={xAxisKey}
              tick={{ fontSize: 12 }}
              stroke="#94a3b8"
            />
            <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
            <Tooltip contentStyle={tooltipStyle} />
            {showLegend && <Legend />}
            {dataKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[index % colors.length]}
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
                animationDuration={1000}
                animationEasing="ease-in-out"
              />
            ))}
          </LineChart>
        );

      case 'bar':
        return (
          <BarChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />}
            <XAxis
              dataKey={xAxisKey}
              tick={{ fontSize: 12 }}
              stroke="#94a3b8"
            />
            <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
            <Tooltip contentStyle={tooltipStyle} />
            {showLegend && <Legend />}
            {dataKeys.map((key, index) => (
              <Bar
                key={key}
                dataKey={key}
                fill={colors[index % colors.length]}
                radius={[8, 8, 0, 0]}
                animationDuration={1000}
                animationEasing="ease-in-out"
              />
            ))}
          </BarChart>
        );

      case 'area':
        return (
          <AreaChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />}
            <XAxis
              dataKey={xAxisKey}
              tick={{ fontSize: 12 }}
              stroke="#94a3b8"
            />
            <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
            <Tooltip contentStyle={tooltipStyle} />
            {showLegend && <Legend />}
            {dataKeys.map((key, index) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[index % colors.length]}
                fill={colors[index % colors.length]}
                fillOpacity={0.3}
                animationDuration={1000}
                animationEasing="ease-in-out"
              />
            ))}
          </AreaChart>
        );

      default:
        return null;
    }
  };

  return (
    <motion.div
      className="card"
      variants={chartVariants}
      initial="hidden"
      animate="visible"
      whileHover={{ boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)' }}
    >
      {title && (
        <motion.h3
          className="text-lg font-semibold text-dark-900 mb-4"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          {title}
        </motion.h3>
      )}

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        <ResponsiveContainer width="100%" height={height}>
          {renderChart()}
        </ResponsiveContainer>
      </motion.div>
    </motion.div>
  );
}

// Specialized chart for telemetry trends
export function TelemetryChart({ data, metrics = ['engine_temp', 'vibration', 'engine_rpm'] }) {
  return (
    <AnimatedChart
      data={data}
      type="line"
      title="Telemetry Trends"
      dataKeys={metrics}
      height={350}
      colors={['#ef4444', '#f59e0b', '#0ea5e9']}
      xAxisKey="timestamp"
    />
  );
}

// Alert severity distribution chart
export function AlertDistributionChart({ data }) {
  return (
    <AnimatedChart
      data={data}
      type="bar"
      title="Alert Distribution by Severity"
      dataKeys={['count']}
      height={300}
      colors={['#0ea5e9']}
      xAxisKey="severity"
    />
  );
}

// Component failure trends
export function ComponentTrendsChart({ data }) {
  return (
    <AnimatedChart
      data={data}
      type="area"
      title="Component Failure Trends"
      dataKeys={['cooling_system', 'engine_mount', 'electrical_system']}
      height={300}
      colors={['#3b82f6', '#f59e0b', '#ef4444']}
      xAxisKey="date"
    />
  );
}
