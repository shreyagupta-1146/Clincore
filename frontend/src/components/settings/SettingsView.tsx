import { User, Shield, Bell } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export function SettingsView() {
  const { user } = useAuth();

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h2 className="text-2xl font-serif font-semibold text-medical-navy-500">Settings</h2>
        <p className="text-sm text-medical-neutral-500 mt-1">
          Manage your account preferences and security settings
        </p>
      </div>

      <div className="space-y-6">
        <div className="bg-white border border-medical-neutral-200 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-medical-navy-50 p-2 rounded-lg">
              <User className="w-5 h-5 text-medical-navy-500" />
            </div>
            <h3 className="text-lg font-semibold text-medical-navy-500">Account Information</h3>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
                Full Name
              </label>
              <input
                type="text"
                defaultValue={user?.user_metadata?.name || 'Not set'}
                className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
                Email Address
              </label>
              <input
                type="email"
                value={user?.email || ''}
                disabled
                className="w-full px-3 py-2 border border-medical-neutral-300 rounded bg-medical-neutral-50 text-medical-neutral-600"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
                Role / Position
              </label>
              <input
                type="text"
                defaultValue="Physician"
                className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
              />
            </div>
          </div>

          <div className="mt-6 pt-6 border-t border-medical-neutral-200">
            <button className="px-4 py-2.5 bg-medical-navy-500 text-white rounded-lg hover:bg-medical-navy-600 transition-colors font-medium">
              Save Changes
            </button>
          </div>
        </div>

        <div className="bg-white border border-medical-neutral-200 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-medical-teal-50 p-2 rounded-lg">
              <Shield className="w-5 h-5 text-medical-teal-600" />
            </div>
            <h3 className="text-lg font-semibold text-medical-navy-500">Security</h3>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-3">
              <div>
                <p className="font-medium text-medical-neutral-800">Two-Factor Authentication</p>
                <p className="text-sm text-medical-neutral-600">
                  Add an extra layer of security to your account
                </p>
              </div>
              <button className="px-4 py-2 border border-medical-neutral-300 rounded-lg hover:bg-medical-neutral-50 transition-colors font-medium text-sm">
                Enable
              </button>
            </div>

            <div className="border-t border-medical-neutral-200 pt-4">
              <button className="text-sm font-medium text-medical-teal-600 hover:text-medical-teal-700">
                Change Password
              </button>
            </div>
          </div>
        </div>

        <div className="bg-white border border-medical-neutral-200 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-medical-sage-50 p-2 rounded-lg">
              <Bell className="w-5 h-5 text-medical-sage-600" />
            </div>
            <h3 className="text-lg font-semibold text-medical-navy-500">Notifications</h3>
          </div>

          <div className="space-y-3">
            <label className="flex items-center justify-between cursor-pointer py-2">
              <div>
                <p className="font-medium text-medical-neutral-800">Email Notifications</p>
                <p className="text-sm text-medical-neutral-600">
                  Receive email alerts for shared folders
                </p>
              </div>
              <input
                type="checkbox"
                defaultChecked
                className="w-5 h-5 text-medical-teal-600 border-medical-neutral-300 rounded focus:ring-medical-teal-500"
              />
            </label>

            <label className="flex items-center justify-between cursor-pointer py-2">
              <div>
                <p className="font-medium text-medical-neutral-800">Security Alerts</p>
                <p className="text-sm text-medical-neutral-600">
                  Get notified of unusual account activity
                </p>
              </div>
              <input
                type="checkbox"
                defaultChecked
                className="w-5 h-5 text-medical-teal-600 border-medical-neutral-300 rounded focus:ring-medical-teal-500"
              />
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
