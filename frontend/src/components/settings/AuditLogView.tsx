import { useEffect, useState } from 'react';
import { Shield, FolderOpen, MessageSquare, Share2, Clock } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { AuditLog } from '../../lib/types';
import { useAuth } from '../../contexts/AuthContext';

export function AuditLogView() {
  const { user } = useAuth();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    loadAuditLogs();
  }, [user]);

  const loadAuditLogs = async () => {
    if (!user) return;

    const { data, error } = await supabase
      .from('audit_logs')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(100);

    if (!error && data) {
      setLogs(data);
    }
    setLoading(false);
  };

  const filteredLogs = filter === 'all' ? logs : logs.filter((log) => log.resource_type === filter);

  const getActionIcon = (resourceType: string) => {
    switch (resourceType) {
      case 'folder':
        return FolderOpen;
      case 'chat':
        return MessageSquare;
      case 'share':
        return Share2;
      case 'auth':
        return Shield;
      default:
        return Clock;
    }
  };

  const getActionColor = (action: string) => {
    if (action.includes('create')) return 'text-success';
    if (action.includes('delete')) return 'text-error';
    if (action.includes('share')) return 'text-medical-teal-600';
    return 'text-medical-neutral-600';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-medical-neutral-500">Loading audit logs...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-serif font-semibold text-medical-navy-500">Audit Logs</h2>
          <p className="text-sm text-medical-neutral-500 mt-1">
            View all security and activity logs for your account
          </p>
        </div>

        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-4 py-2 border border-medical-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical-teal-500 text-sm"
        >
          <option value="all">All Actions</option>
          <option value="folder">Folders</option>
          <option value="chat">Chats</option>
          <option value="share">Sharing</option>
          <option value="auth">Authentication</option>
        </select>
      </div>

      <div className="bg-white border border-medical-neutral-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-medical-neutral-50 border-b border-medical-neutral-200">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-semibold text-medical-neutral-700 uppercase">
                  Timestamp
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-medical-neutral-700 uppercase">
                  Action
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-medical-neutral-700 uppercase">
                  Resource
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-medical-neutral-700 uppercase">
                  Details
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-medical-neutral-200">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-sm text-medical-neutral-500">
                    No audit logs found
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => {
                  const Icon = getActionIcon(log.resource_type);
                  const timestamp = new Date(log.created_at);
                  return (
                    <tr key={log.id} className="hover:bg-medical-neutral-50">
                      <td className="px-6 py-4 text-sm text-medical-neutral-700">
                        <div>{timestamp.toLocaleDateString()}</div>
                        <div className="text-xs text-medical-neutral-500">
                          {timestamp.toLocaleTimeString()}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <Icon className={`w-4 h-4 ${getActionColor(log.action)}`} />
                          <span className="text-sm font-medium text-medical-neutral-800">
                            {log.action.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2.5 py-1 rounded bg-medical-neutral-100 text-xs font-medium text-medical-neutral-700">
                          {log.resource_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-medical-neutral-600">
                        {Object.keys(log.details).length > 0 ? (
                          <div className="max-w-md">
                            {Object.entries(log.details)
                              .slice(0, 2)
                              .map(([key, value]) => (
                                <div key={key} className="text-xs">
                                  <span className="font-medium">{key}:</span> {String(value)}
                                </div>
                              ))}
                          </div>
                        ) : (
                          <span className="text-medical-neutral-400">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
