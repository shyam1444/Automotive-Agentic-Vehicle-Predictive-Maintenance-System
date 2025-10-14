import { motion, AnimatePresence } from 'framer-motion';
import { ArrowUp, ArrowDown, AlertCircle } from 'lucide-react';
import { useState } from 'react';
import { format } from 'date-fns';

const priorityConfig = {
  low: { color: 'success', label: 'Low' },
  medium: { color: 'warning', label: 'Medium' },
  high: { color: 'danger', label: 'High' },
  critical: { color: 'danger', label: 'Critical' },
};

export default function CAPATable({ data, onRowClick }) {
  const [sortField, setSortField] = useState('timestamp');
  const [sortDirection, setSortDirection] = useState('desc');

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const sortedData = [...data].sort((a, b) => {
    const aVal = a[sortField];
    const bVal = b[sortField];
    
    if (sortDirection === 'asc') {
      return aVal > bVal ? 1 : -1;
    } else {
      return aVal < bVal ? 1 : -1;
    }
  });

  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-4 h-4 ml-1" />
    ) : (
      <ArrowDown className="w-4 h-4 ml-1" />
    );
  };

  return (
    <motion.div
      className="card overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-dark-50 border-b border-dark-200">
            <tr>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-dark-700 uppercase tracking-wider cursor-pointer hover:bg-dark-100 transition-colors"
                onClick={() => handleSort('timestamp')}
              >
                <div className="flex items-center">
                  Date
                  <SortIcon field="timestamp" />
                </div>
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-dark-700 uppercase tracking-wider cursor-pointer hover:bg-dark-100 transition-colors"
                onClick={() => handleSort('component')}
              >
                <div className="flex items-center">
                  Component
                  <SortIcon field="component" />
                </div>
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-dark-700 uppercase tracking-wider">
                Issue
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-dark-700 uppercase tracking-wider cursor-pointer hover:bg-dark-100 transition-colors"
                onClick={() => handleSort('priority')}
              >
                <div className="flex items-center">
                  Priority
                  <SortIcon field="priority" />
                </div>
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-dark-700 uppercase tracking-wider cursor-pointer hover:bg-dark-100 transition-colors"
                onClick={() => handleSort('failure_count')}
              >
                <div className="flex items-center">
                  Failures
                  <SortIcon field="failure_count" />
                </div>
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-dark-700 uppercase tracking-wider">
                Recommendation
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-dark-100">
            <AnimatePresence mode="popLayout">
              {sortedData.map((item, index) => {
                const priorityConf = priorityConfig[item.priority] || priorityConfig.medium;
                
                return (
                  <motion.tr
                    key={item.id || index}
                    className="hover:bg-dark-50 cursor-pointer transition-colors"
                    onClick={() => onRowClick && onRowClick(item)}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{
                      delay: index * 0.03,
                      type: 'spring',
                      stiffness: 500,
                      damping: 30,
                    }}
                    whileHover={{ scale: 1.01, backgroundColor: '#f8fafc' }}
                    layout
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-dark-900">
                      {item.timestamp
                        ? format(new Date(item.timestamp), 'MMM dd, yyyy')
                        : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <AlertCircle className="w-4 h-4 text-warning-500 mr-2" />
                        <span className="text-sm font-medium text-dark-900">
                          {item.component || 'Unknown'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-dark-900 max-w-xs truncate">
                        {item.issue_description || item.description || 'No description'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <motion.span
                        className={`badge badge-${priorityConf.color}`}
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: index * 0.03 + 0.2 }}
                      >
                        {priorityConf.label}
                      </motion.span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <motion.div
                        className="text-sm font-semibold text-dark-900"
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: index * 0.03 + 0.3 }}
                      >
                        {item.failure_count || 0}
                      </motion.div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-dark-700 max-w-md truncate">
                        {item.recommendation || 'Under review'}
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>
          </tbody>
        </table>

        {sortedData.length === 0 && (
          <motion.div
            className="text-center py-12"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <AlertCircle className="w-16 h-16 text-dark-300 mx-auto mb-4" />
            <p className="text-lg font-medium text-dark-900 mb-1">
              No CAPA data available
            </p>
            <p className="text-sm text-dark-500">
              Component failure reports will appear here
            </p>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
