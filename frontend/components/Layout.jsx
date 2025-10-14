import { motion } from 'framer-motion';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  LayoutDashboard,
  Car,
  Wrench,
  Factory,
  Shield,
  BarChart3,
  Menu,
  X,
  Bell,
  Settings,
} from 'lucide-react';
import useStore from '../store/useStore';
import { useState } from 'react';

const navigation = [
  { name: 'Dashboard', href: '/vehicle-dashboard', icon: LayoutDashboard },
  { name: 'Fleet', href: '/fleet', icon: Car },
  { name: 'Maintenance', href: '/maintenance', icon: Wrench },
  { name: 'Manufacturing', href: '/manufacturing', icon: Factory },
  { name: 'Security', href: '/security', icon: Shield },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
];

export default function Layout({ children }) {
  const router = useRouter();
  const { sidebarOpen, toggleSidebar, notifications, wsConnected } = useStore();
  const [showNotifications, setShowNotifications] = useState(false);

  return (
    <div className="min-h-screen bg-dark-50">
      {/* Sidebar */}
      <motion.aside
        className={`fixed inset-y-0 left-0 z-50 bg-white border-r border-dark-200 transition-all duration-300 ${
          sidebarOpen ? 'w-64' : 'w-20'
        }`}
        initial={false}
        animate={{ width: sidebarOpen ? 256 : 80 }}
      >
        {/* Logo */}
        <div className="flex items-center justify-between p-4 border-b border-dark-200">
          <motion.div
            className="flex items-center space-x-3"
            animate={{ opacity: sidebarOpen ? 1 : 0 }}
          >
            <Car className="w-8 h-8 text-primary-600" />
            {sidebarOpen && (
              <span className="font-bold text-lg text-dark-900">AutoMaint</span>
            )}
          </motion.div>
          
          <motion.button
            onClick={toggleSidebar}
            className="p-2 rounded-lg hover:bg-dark-100 transition-colors"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            {sidebarOpen ? (
              <X className="w-5 h-5 text-dark-600" />
            ) : (
              <Menu className="w-5 h-5 text-dark-600" />
            )}
          </motion.button>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-2">
          {navigation.map((item) => {
            const isActive = router.pathname === item.href;
            const Icon = item.icon;

            return (
              <Link href={item.href} key={item.name}>
                <motion.div
                  className={`flex items-center space-x-3 p-3 rounded-lg transition-colors cursor-pointer ${
                    isActive
                      ? 'bg-primary-50 text-primary-600'
                      : 'text-dark-600 hover:bg-dark-100'
                  }`}
                  whileHover={{ x: 5 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <Icon className="w-5 h-5" />
                  {sidebarOpen && (
                    <motion.span
                      className="font-medium"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.1 }}
                    >
                      {item.name}
                    </motion.span>
                  )}
                </motion.div>
              </Link>
            );
          })}
        </nav>

        {/* Connection Status */}
        <motion.div
          className={`absolute bottom-4 left-4 right-4 p-3 rounded-lg ${
            wsConnected ? 'bg-success-50' : 'bg-warning-50'
          }`}
          initial={{ opacity: 0 }}
          animate={{ opacity: sidebarOpen ? 1 : 0 }}
        >
          <div className="flex items-center space-x-2">
            <div
              className={`w-2 h-2 rounded-full ${
                wsConnected ? 'bg-success-500' : 'bg-warning-500'
              } animate-pulse`}
            />
            {sidebarOpen && (
              <span className="text-xs font-medium text-dark-700">
                {wsConnected ? 'Live Updates' : 'Connecting...'}
              </span>
            )}
          </div>
        </motion.div>
      </motion.aside>

      {/* Main Content */}
      <div
        className={`transition-all duration-300 ${
          sidebarOpen ? 'ml-64' : 'ml-20'
        }`}
      >
        {/* Header */}
        <header className="bg-white border-b border-dark-200 sticky top-0 z-40">
          <div className="flex items-center justify-between p-4">
            <div>
              <h1 className="text-2xl font-bold text-dark-900">
                Automotive Predictive Maintenance
              </h1>
              <p className="text-sm text-dark-500">
                Real-time vehicle health monitoring and analytics
              </p>
            </div>

            <div className="flex items-center space-x-4">
              {/* Notifications */}
              <div className="relative">
                <motion.button
                  className="relative p-2 rounded-lg hover:bg-dark-100 transition-colors"
                  onClick={() => setShowNotifications(!showNotifications)}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <Bell className="w-5 h-5 text-dark-600" />
                  {notifications.length > 0 && (
                    <motion.span
                      className="absolute -top-1 -right-1 bg-danger-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: 'spring' }}
                    >
                      {notifications.length}
                    </motion.span>
                  )}
                </motion.button>

                {/* Notifications Dropdown */}
                {showNotifications && (
                  <motion.div
                    className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-xl border border-dark-200 max-h-96 overflow-y-auto"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <div className="p-4 border-b border-dark-200">
                      <h3 className="font-semibold text-dark-900">
                        Notifications
                      </h3>
                    </div>
                    <div className="divide-y divide-dark-100">
                      {notifications.length === 0 ? (
                        <p className="p-4 text-sm text-dark-500 text-center">
                          No new notifications
                        </p>
                      ) : (
                        notifications.map((notif) => (
                          <div key={notif.id} className="p-3 hover:bg-dark-50">
                            <p className="text-sm text-dark-900">
                              {notif.message}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </div>

              {/* Settings */}
              <motion.button
                className="p-2 rounded-lg hover:bg-dark-100 transition-colors"
                whileHover={{ scale: 1.05, rotate: 90 }}
                whileTap={{ scale: 0.95 }}
              >
                <Settings className="w-5 h-5 text-dark-600" />
              </motion.button>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}
