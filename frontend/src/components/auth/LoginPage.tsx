import { useState } from 'react';
import { Shield } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export function LoginPage() {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { signIn, signUp } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isSignUp) {
        const { error } = await signUp(email, password, name);
        if (error) setError(error.message);
      } else {
        const { error } = await signIn(email, password);
        if (error) setError(error.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-medical-neutral-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-lg shadow-md border border-medical-neutral-200 p-8">
          <div className="flex items-center justify-center mb-6">
            <div className="bg-medical-navy-500 p-3 rounded-lg">
              <Shield className="w-8 h-8 text-white" />
            </div>
          </div>

          <h1 className="text-2xl font-serif font-semibold text-medical-navy-500 text-center mb-2">
            Medical AI Platform
          </h1>
          <p className="text-medical-neutral-500 text-center mb-8 text-sm">
            Secure clinical decision support system
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignUp && (
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-medical-neutral-700 mb-1">
                  Full Name
                </label>
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500 focus:border-transparent"
                  placeholder="Dr. John Smith"
                  required
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-medical-neutral-700 mb-1">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500 focus:border-transparent"
                placeholder="doctor@hospital.com"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-medical-neutral-700 mb-1">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-medical-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-medical-teal-500 focus:border-transparent"
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>

            {error && (
              <div className="bg-error-light/10 border border-error-light rounded px-3 py-2">
                <p className="text-sm text-error">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-medical-navy-500 text-white py-2.5 rounded font-medium hover:bg-medical-navy-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Processing...' : isSignUp ? 'Create Account' : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsSignUp(!isSignUp);
                setError('');
              }}
              className="text-sm text-medical-teal-500 hover:text-medical-teal-600 font-medium"
            >
              {isSignUp ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
            </button>
          </div>

          <div className="mt-6 pt-6 border-t border-medical-neutral-200">
            <div className="flex items-center gap-2 text-xs text-medical-neutral-500">
              <Shield className="w-3.5 h-3.5" />
              <span>End-to-end encrypted, HIPAA compliant</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
