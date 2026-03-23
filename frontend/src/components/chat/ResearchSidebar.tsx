import { useState } from 'react';
import { FileText, AlertTriangle, GitBranch, ExternalLink, TrendingUp } from 'lucide-react';
import { MessageWithAI } from '../../lib/types';

interface ResearchSidebarProps {
  message?: MessageWithAI;
}

type Tab = 'differential' | 'research' | 'explainability';

export function ResearchSidebar({ message }: ResearchSidebarProps) {
  const [activeTab, setActiveTab] = useState<Tab>('differential');

  const aiResponse = message?.ai_responses?.[0];
  const researchPapers = message?.research_papers || [];

  const tabs = [
    { id: 'differential' as const, label: 'Differential & Red Flags', icon: AlertTriangle },
    { id: 'research' as const, label: 'Research & Cases', icon: FileText },
    { id: 'explainability' as const, label: 'Reasoning Chain', icon: GitBranch },
  ];

  return (
    <aside className="w-96 bg-white border-l border-medical-neutral-200 flex flex-col h-full">
      <div className="border-b border-medical-neutral-200">
        <div className="flex">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === tab.id
                    ? 'border-medical-teal-500 text-medical-teal-600 bg-medical-teal-50/50'
                    : 'border-transparent text-medical-neutral-600 hover:text-medical-neutral-800 hover:bg-medical-neutral-50'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden xl:inline">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {!message ? (
          <div className="text-center py-12">
            <div className="bg-medical-neutral-100 w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3">
              <FileText className="w-6 h-6 text-medical-neutral-400" />
            </div>
            <p className="text-sm text-medical-neutral-500">
              Select an AI message to view analysis
            </p>
          </div>
        ) : (
          <>
            {activeTab === 'differential' && aiResponse && (
              <DifferentialTab aiResponse={aiResponse} />
            )}
            {activeTab === 'research' && <ResearchTab papers={researchPapers} />}
            {activeTab === 'explainability' && aiResponse && (
              <ExplainabilityTab aiResponse={aiResponse} />
            )}
          </>
        )}
      </div>
    </aside>
  );
}

function DifferentialTab({ aiResponse }: { aiResponse: NonNullable<MessageWithAI['ai_responses']>[0] }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-medical-navy-500 mb-3">Primary Suggestion</h3>
        <div className="bg-medical-teal-50 border border-medical-teal-200 rounded-lg p-4">
          <p className="text-sm font-medium text-medical-teal-900 mb-2">
            {aiResponse.primary_suggestion}
          </p>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-medical-teal-600" />
            <span className="text-xs text-medical-teal-700">
              Confidence: {((aiResponse.confidence || 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {aiResponse.differential_diagnoses && aiResponse.differential_diagnoses.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-medical-navy-500 mb-3">
            Differential Diagnoses
          </h3>
          <div className="space-y-2">
            {aiResponse.differential_diagnoses.map((diff, index) => (
              <div
                key={index}
                className="bg-white border border-medical-neutral-200 rounded-lg p-3"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-medical-neutral-800">
                    {diff.diagnosis}
                  </span>
                  <span className="text-xs text-medical-neutral-600">
                    {(diff.probability * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-medical-neutral-100 rounded-full h-1.5">
                  <div
                    className="bg-medical-teal-500 h-1.5 rounded-full"
                    style={{ width: `${diff.probability * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {aiResponse.red_flags && aiResponse.red_flags.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-medical-navy-500 mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-error" />
            Red Flags
          </h3>
          <ul className="space-y-2">
            {aiResponse.red_flags.map((flag, index) => (
              <li
                key={index}
                className="flex items-start gap-2 text-sm text-medical-neutral-700 bg-error-light/5 border border-error-light/20 rounded p-2"
              >
                <span className="text-error mt-0.5">•</span>
                <span>{flag}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {aiResponse.missing_information && aiResponse.missing_information.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-medical-navy-500 mb-3">
            Missing Information
          </h3>
          <ul className="space-y-2">
            {aiResponse.missing_information.map((info, index) => (
              <li
                key={index}
                className="flex items-start gap-2 text-sm text-medical-neutral-700 bg-warning-light/10 border border-warning-light/30 rounded p-2"
              >
                <span className="text-warning-dark mt-0.5">•</span>
                <span>{info}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ResearchTab({ papers }: { papers: MessageWithAI['research_papers'] }) {
  if (!papers || papers.length === 0) {
    return (
      <div className="text-center py-12">
        <FileText className="w-12 h-12 text-medical-neutral-300 mx-auto mb-3" />
        <p className="text-sm text-medical-neutral-500">
          No research papers available for this message
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {papers.map((paper) => (
        <div
          key={paper.id}
          className="bg-white border border-medical-neutral-200 rounded-lg p-4 hover:border-medical-teal-300 transition-colors"
        >
          <h4 className="text-sm font-semibold text-medical-navy-500 mb-1">{paper.title}</h4>
          {paper.source && (
            <p className="text-xs text-medical-neutral-500 mb-3">{paper.source}</p>
          )}
          {paper.tldr && (
            <p className="text-sm text-medical-neutral-700 leading-body mb-3">{paper.tldr}</p>
          )}
          {paper.url && (
            <a
              href={paper.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-medical-teal-600 hover:text-medical-teal-700"
            >
              Read full paper
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

function ExplainabilityTab({ aiResponse }: { aiResponse: NonNullable<MessageWithAI['ai_responses']>[0] }) {
  if (!aiResponse.reasoning_chain || aiResponse.reasoning_chain.length === 0) {
    return (
      <div className="text-center py-12">
        <GitBranch className="w-12 h-12 text-medical-neutral-300 mx-auto mb-3" />
        <p className="text-sm text-medical-neutral-500">
          No reasoning chain available for this message
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {aiResponse.reasoning_chain.map((step, index) => (
        <div key={index} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className="w-8 h-8 bg-medical-teal-500 text-white rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0">
              {step.step}
            </div>
            {index < aiResponse.reasoning_chain.length - 1 && (
              <div className="w-0.5 bg-medical-teal-200 flex-1 my-1" />
            )}
          </div>
          <div className="flex-1 pb-6">
            <p className="text-sm text-medical-neutral-700 leading-body">{step.description}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
