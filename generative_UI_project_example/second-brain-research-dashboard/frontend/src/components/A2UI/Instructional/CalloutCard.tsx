/**
 * CalloutCard Component
 *
 * Displays informational callouts with type-specific styling and colors.
 * Supports tip, warning, info, and danger variants with appropriate visual indicators.
 */

import React from 'react';
import { Card, CardContent } from "@/components/ui/card";

export interface CalloutCardProps {
  /** Callout type determining color scheme and icon */
  type: 'tip' | 'warning' | 'info' | 'danger' | 'success' | 'error' | 'note' | string;

  /** Callout title */
  title: string;

  /** Callout content/message */
  content: string;

  /** Optional custom icon (overrides default type icon) */
  icon?: string;
}

/**
 * CalloutCard Component
 *
 * A card component for displaying informational callouts with color-coded
 * backgrounds and borders based on the callout type.
 */
export function CalloutCard({
  type,
  title,
  content,
  icon,
}: CalloutCardProps): React.ReactElement {
  const typeConfig: Record<string, { bgColor: string; borderColor: string; icon: string; iconBg: string; titleColor: string }> = {
    tip: {
      bgColor: 'bg-gradient-to-br from-card to-secondary/30',
      borderColor: 'border-l-4 border-blue-500 dark:border-blue-500/70',
      icon: '💡',
      iconBg: 'bg-blue-500/30 dark:bg-blue-500/40',
      titleColor: 'text-blue-300',
    },
    warning: {
      bgColor: 'bg-gradient-to-br from-card to-secondary/30',
      borderColor: 'border-l-4 border-yellow-500 dark:border-yellow-500/70',
      icon: '⚠️',
      iconBg: 'bg-yellow-500/30 dark:bg-yellow-500/40',
      titleColor: 'text-yellow-300',
    },
    info: {
      bgColor: 'bg-gradient-to-br from-card to-secondary/30',
      borderColor: 'border-l-4 border-blue-400 dark:border-blue-400/70',
      icon: 'ℹ️',
      iconBg: 'bg-blue-400/30 dark:bg-blue-400/40',
      titleColor: 'text-blue-200',
    },
    danger: {
      bgColor: 'bg-gradient-to-br from-card to-secondary/30',
      borderColor: 'border-l-4 border-red-500 dark:border-red-500/70',
      icon: '🚨',
      iconBg: 'bg-red-500/30 dark:bg-red-500/40',
      titleColor: 'text-red-300',
    },
    // Backend compatibility types
    success: {
      bgColor: 'bg-gradient-to-br from-card to-secondary/30',
      borderColor: 'border-l-4 border-emerald-500 dark:border-emerald-500/70',
      icon: '✅',
      iconBg: 'bg-emerald-500/30 dark:bg-emerald-500/40',
      titleColor: 'text-emerald-300',
    },
    error: {
      bgColor: 'bg-gradient-to-br from-card to-secondary/30',
      borderColor: 'border-l-4 border-red-500 dark:border-red-500/70',
      icon: '🚨',
      iconBg: 'bg-red-500/30 dark:bg-red-500/40',
      titleColor: 'text-red-300',
    },
    note: {
      bgColor: 'bg-gradient-to-br from-card to-secondary/30',
      borderColor: 'border-l-4 border-slate-400 dark:border-slate-400/70',
      icon: '📝',
      iconBg: 'bg-slate-400/30 dark:bg-slate-400/40',
      titleColor: 'text-slate-300',
    },
  };

  // Default to 'info' config for unknown types
  const config = typeConfig[type] || typeConfig.info;
  const displayIcon = icon || config.icon;

  return (
    <Card className={`${config.bgColor} ${config.borderColor} dark:border-blue-500/20`}>
      <CardContent className="pt-6">
        <div className="flex items-start gap-3">
          <div className={`flex items-center justify-center w-8 h-8 rounded-full ${config.iconBg} shrink-0`}>
            <span className="text-lg">{displayIcon}</span>
          </div>
          <div className="flex-1 space-y-1">
            <div className={`font-semibold ${config.titleColor}`}>{title}</div>
            <p className="text-sm text-slate-200">{content}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default CalloutCard;
