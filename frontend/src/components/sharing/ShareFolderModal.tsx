import { useState } from 'react';
import { X, ArrowRight, ArrowLeft, Shield, CheckCircle } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { useAuth } from '../../contexts/AuthContext';

interface ShareFolderModalProps {
  folderId: string;
  folderName: string;
  onClose: () => void;
  onSuccess: () => void;
}

type Step = 'recipient' | 'security' | 'confirm' | 'success';

export function ShareFolderModal({
  folderId,
  folderName,
  onClose,
  onSuccess,
}: ShareFolderModalProps) {
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState<Step>('recipient');
  const [recipientName, setRecipientName] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [recipientRole, setRecipientRole] = useState('');
  const [requiresAuth, setRequiresAuth] = useState(true);
  const [loading, setLoading] = useState(false);

  const handleShare = async () => {
    if (!user) return;

    setLoading(true);
    const { error: shareError } = await supabase.from('folder_shares').insert({
      folder_id: folderId,
      shared_by: user.id,
      shared_with_email: recipientEmail,
      shared_with_name: recipientName,
      shared_with_role: recipientRole,
    });

    if (requiresAuth) {
      await supabase
        .from('folders')
        .update({ requires_auth: true, status: 'Shared' })
        .eq('id', folderId);
    } else {
      await supabase.from('folders').update({ status: 'Shared' }).eq('id', folderId);
    }

    await supabase.from('audit_logs').insert({
      user_id: user.id,
      action: 'share_folder',
      resource_type: 'share',
      resource_id: folderId,
      details: {
        shared_with: recipientEmail,
        requires_auth: requiresAuth,
      },
    });

    setLoading(false);
    if (!shareError) {
      setCurrentStep('success');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4">
        <div className="flex items-center justify-between border-b border-medical-neutral-200 px-6 py-4">
          <div>
            <h2 className="text-xl font-serif font-semibold text-medical-navy-500">
              Share Folder
            </h2>
            <p className="text-sm text-medical-neutral-500 mt-1">{folderName}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-medical-neutral-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-medical-neutral-600" />
          </button>
        </div>

        <div className="px-6 py-4 border-b border-medical-neutral-200">
          <div className="flex items-center justify-between max-w-md mx-auto">
            {['recipient', 'security', 'confirm'].map((step, index) => (
              <div key={step} className="flex items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
                    currentStep === step ||
                    (step === 'security' &&
                      ['security', 'confirm', 'success'].includes(currentStep)) ||
                    (step === 'confirm' && ['confirm', 'success'].includes(currentStep))
                      ? 'bg-medical-teal-500 text-white'
                      : 'bg-medical-neutral-200 text-medical-neutral-600'
                  }`}
                >
                  {index + 1}
                </div>
                {index < 2 && (
                  <div
                    className={`w-24 h-0.5 mx-2 ${
                      (step === 'recipient' &&
                        ['security', 'confirm', 'success'].includes(currentStep)) ||
                      (step === 'security' && ['confirm', 'success'].includes(currentStep))
                        ? 'bg-medical-teal-500'
                        : 'bg-medical-neutral-200'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="p-6 min-h-[300px]">
          {currentStep === 'recipient' && (
            <RecipientStep
              recipientName={recipientName}
              recipientEmail={recipientEmail}
              recipientRole={recipientRole}
              onNameChange={setRecipientName}
              onEmailChange={setRecipientEmail}
              onRoleChange={setRecipientRole}
              onNext={() => setCurrentStep('security')}
            />
          )}

          {currentStep === 'security' && (
            <SecurityStep
              requiresAuth={requiresAuth}
              onRequiresAuthChange={setRequiresAuth}
              onBack={() => setCurrentStep('recipient')}
              onNext={() => setCurrentStep('confirm')}
            />
          )}

          {currentStep === 'confirm' && (
            <ConfirmStep
              recipientName={recipientName}
              recipientEmail={recipientEmail}
              recipientRole={recipientRole}
              requiresAuth={requiresAuth}
              folderName={folderName}
              loading={loading}
              onBack={() => setCurrentStep('security')}
              onConfirm={handleShare}
            />
          )}

          {currentStep === 'success' && (
            <SuccessStep
              recipientName={recipientName}
              onClose={() => {
                onSuccess();
                onClose();
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function RecipientStep({
  recipientName,
  recipientEmail,
  recipientRole,
  onNameChange,
  onEmailChange,
  onRoleChange,
  onNext,
}: {
  recipientName: string;
  recipientEmail: string;
  recipientRole: string;
  onNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onRoleChange: (value: string) => void;
  onNext: () => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-medical-navy-500 mb-2">Recipient Details</h3>
        <p className="text-sm text-medical-neutral-600">
          Enter the details of the specialist you want to share this folder with
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
            Recipient Name
          </label>
          <input
            type="text"
            value={recipientName}
            onChange={(e) => onNameChange(e.target.value)}
            className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
            placeholder="Dr. Sarah Johnson"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
            Email Address
          </label>
          <input
            type="email"
            value={recipientEmail}
            onChange={(e) => onEmailChange(e.target.value)}
            className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
            placeholder="sarah.johnson@hospital.com"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-medical-neutral-700 mb-1">
            Role / Position
          </label>
          <input
            type="text"
            value={recipientRole}
            onChange={(e) => onRoleChange(e.target.value)}
            className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500"
            placeholder="Consultant Cardiologist, Apollo Hospital"
          />
        </div>
      </div>

      <div className="flex justify-end pt-4">
        <button
          onClick={onNext}
          disabled={!recipientName || !recipientEmail}
          className="flex items-center gap-2 px-5 py-2.5 bg-medical-navy-500 text-white rounded-lg hover:bg-medical-navy-600 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

function SecurityStep({
  requiresAuth,
  onRequiresAuthChange,
  onBack,
  onNext,
}: {
  requiresAuth: boolean;
  onRequiresAuthChange: (value: boolean) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-medical-navy-500 mb-2">Security Settings</h3>
        <p className="text-sm text-medical-neutral-600">
          Configure access control for this shared folder
        </p>
      </div>

      <div className="bg-medical-teal-50 border border-medical-teal-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Shield className="w-5 h-5 text-medical-teal-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <p className="font-medium text-medical-teal-900 mb-1">
                  Require folder-level authentication
                </p>
                <p className="text-sm text-medical-teal-700">
                  The recipient must re-authenticate before viewing this folder
                </p>
              </div>
              <input
                type="checkbox"
                checked={requiresAuth}
                onChange={(e) => onRequiresAuthChange(e.target.checked)}
                className="w-5 h-5 text-medical-teal-600 border-medical-teal-300 rounded focus:ring-medical-teal-500"
              />
            </label>
          </div>
        </div>
      </div>

      <div className="bg-medical-neutral-50 border border-medical-neutral-200 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-medical-neutral-800 mb-2">
          What is folder-level authentication?
        </h4>
        <p className="text-sm text-medical-neutral-600 leading-body">
          When enabled, the recipient will need to verify their identity through multi-factor
          authentication before accessing this folder. This provides an additional security layer
          for sensitive medical cases.
        </p>
      </div>

      <div className="flex justify-between pt-4">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-5 py-2.5 border border-medical-neutral-300 rounded-lg hover:bg-medical-neutral-50 transition-colors font-medium text-medical-neutral-700"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <button
          onClick={onNext}
          className="flex items-center gap-2 px-5 py-2.5 bg-medical-navy-500 text-white rounded-lg hover:bg-medical-navy-600 transition-colors font-medium"
        >
          Next
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

function ConfirmStep({
  recipientName,
  recipientEmail,
  recipientRole,
  requiresAuth,
  folderName,
  loading,
  onBack,
  onConfirm,
}: {
  recipientName: string;
  recipientEmail: string;
  recipientRole: string;
  requiresAuth: boolean;
  folderName: string;
  loading: boolean;
  onBack: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-medical-navy-500 mb-2">Confirm Sharing</h3>
        <p className="text-sm text-medical-neutral-600">
          Please review the sharing details before proceeding
        </p>
      </div>

      <div className="bg-medical-neutral-50 border border-medical-neutral-200 rounded-lg p-5 space-y-4">
        <div>
          <p className="text-xs font-medium text-medical-neutral-500 mb-1">Folder</p>
          <p className="text-sm font-semibold text-medical-neutral-800">{folderName}</p>
        </div>

        <div className="border-t border-medical-neutral-200 pt-4">
          <p className="text-xs font-medium text-medical-neutral-500 mb-1">Recipient</p>
          <p className="text-sm font-semibold text-medical-neutral-800">{recipientName}</p>
          <p className="text-sm text-medical-neutral-600">{recipientEmail}</p>
          {recipientRole && (
            <p className="text-sm text-medical-neutral-600 mt-1">{recipientRole}</p>
          )}
        </div>

        <div className="border-t border-medical-neutral-200 pt-4">
          <p className="text-xs font-medium text-medical-neutral-500 mb-1">Security</p>
          <div className="flex items-center gap-2">
            <Shield
              className={`w-4 h-4 ${requiresAuth ? 'text-medical-teal-600' : 'text-medical-neutral-400'}`}
            />
            <p className="text-sm text-medical-neutral-700">
              {requiresAuth ? 'Folder-level authentication required' : 'Standard access'}
            </p>
          </div>
        </div>
      </div>

      <div className="bg-warning-light/10 border border-warning-light/30 rounded-lg p-4">
        <p className="text-sm text-warning-dark leading-body">
          An audit log entry will be created for this sharing action. The recipient will be
          notified via email.
        </p>
      </div>

      <div className="flex justify-between pt-4">
        <button
          onClick={onBack}
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2.5 border border-medical-neutral-300 rounded-lg hover:bg-medical-neutral-50 transition-colors font-medium text-medical-neutral-700 disabled:opacity-50"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className="px-5 py-2.5 bg-medical-navy-500 text-white rounded-lg hover:bg-medical-navy-600 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Sharing...' : 'Confirm & Share'}
        </button>
      </div>
    </div>
  );
}

function SuccessStep({ recipientName, onClose }: { recipientName: string; onClose: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 space-y-6">
      <div className="w-16 h-16 bg-success-light/20 rounded-full flex items-center justify-center">
        <CheckCircle className="w-10 h-10 text-success" />
      </div>

      <div className="text-center">
        <h3 className="text-xl font-serif font-semibold text-medical-navy-500 mb-2">
          Folder Shared Successfully
        </h3>
        <p className="text-sm text-medical-neutral-600">
          {recipientName} now has access to this folder
        </p>
      </div>

      <div className="bg-medical-neutral-50 border border-medical-neutral-200 rounded-lg p-4 max-w-md">
        <p className="text-sm text-medical-neutral-700 leading-body">
          An email notification has been sent to the recipient. An audit log entry has been
          created for this action.
        </p>
      </div>

      <button
        onClick={onClose}
        className="px-6 py-2.5 bg-medical-navy-500 text-white rounded-lg hover:bg-medical-navy-600 transition-colors font-medium"
      >
        Done
      </button>
    </div>
  );
}
