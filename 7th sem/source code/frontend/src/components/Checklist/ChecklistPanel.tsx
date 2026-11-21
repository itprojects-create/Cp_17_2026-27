import React from 'react';
import type { ChecklistItemType } from '../../types';

type ChecklistPanelProps = {
  checklist: ChecklistItemType[];
  progress: {
    total?: number;
    completed?: number;
    percentage?: number;
  } | null;
  isLoading: boolean;
  onUpdateItem: (itemId: string, status: string) => Promise<void>;
};

const STATUS_OPTIONS = ['Not Started', 'In Progress', 'Completed', 'Blocked'] as const;

export const ChecklistPanel: React.FC<ChecklistPanelProps> = ({
  checklist,
  progress,
  isLoading,
  onUpdateItem,
}) => {
  return (
    <div className="h-full w-[360px] border-l border-gray-200 bg-gray-50">
      <div className="border-b border-gray-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-800">Checklist</h3>
        <p className="text-xs text-gray-600">
          {progress?.completed ?? 0}/{progress?.total ?? checklist.length} completed ({progress?.percentage ?? 0}%)
        </p>
      </div>

      <div className="h-[calc(100%-57px)] overflow-y-auto p-3">
        {isLoading ? (
          <p className="text-sm text-gray-500">Loading checklist...</p>
        ) : checklist.length === 0 ? (
          <p className="text-sm text-gray-500">Checklist will appear after persona detection.</p>
        ) : (
          <div className="space-y-2">
            {checklist.map((item) => (
              <div key={item.id} className="rounded-lg border border-gray-200 bg-white p-3">
                <p className="text-xs font-medium text-gray-500">{item.id}</p>
                <p className="mt-1 text-sm text-gray-800">{item.task}</p>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <span className="text-xs text-gray-500">{item.owner}</span>
                  <select
                    value={item.status}
                    onChange={(e) => onUpdateItem(item.id, e.target.value)}
                    className="rounded border border-gray-300 px-2 py-1 text-xs"
                  >
                    {STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
