/**
 * Custom hook for interacting with the Second Brain dashboard agent.
 *
 * Uses CopilotKit v2's useAgent hook for AG-UI protocol communication
 * with the Pydantic AI backend.
 */

import { useAgent } from "@copilotkit/react-core/v2";
import { useMemo, useCallback } from "react";
import type { A2UIComponent, SemanticZone } from "@/lib/a2ui-catalog";

/**
 * Dashboard state synchronized with backend agent.
 * Must match DashboardState in agent/agent.py
 */
export interface DashboardState {
  markdown_content: string;
  document_title: string;
  document_type: string;
  content_analysis: Record<string, any>;
  layout_type: string;
  components: A2UIComponent[];
  status: "idle" | "analyzing" | "generating" | "complete" | "error";
  progress: number;
  current_step: string;
  activity_log: Array<{
    id: string;
    message: string;
    timestamp: string;
    status: "in_progress" | "completed" | "error";
  }>;
  error_message: string | null;
}

/**
 * Initial state for the dashboard agent.
 */
const initialState: DashboardState = {
  markdown_content: "",
  document_title: "",
  document_type: "",
  content_analysis: {},
  layout_type: "",
  components: [],
  status: "idle",
  progress: 0,
  current_step: "",
  activity_log: [],
  error_message: null,
};

/**
 * Group components by semantic zone for layout.
 */
function groupByZone(components: A2UIComponent[]): Record<SemanticZone, A2UIComponent[]> {
  const groups: Record<SemanticZone, A2UIComponent[]> = {
    hero: [],
    metrics: [],
    insights: [],
    content: [],
    media: [],
    resources: [],
    tags: [],
  };

  for (const comp of components) {
    const zone = (comp.zone as SemanticZone) || "content";
    if (groups[zone]) {
      groups[zone].push(comp);
    } else {
      groups.content.push(comp);
    }
  }

  return groups;
}

/**
 * Hook for dashboard agent interaction using CopilotKit v2's useAgent.
 *
 * Provides:
 * - state: Current dashboard state (synced with backend via AG-UI)
 * - componentsByZone: Components grouped by semantic zone
 * - generateDashboard: Trigger dashboard generation
 * - isGenerating: Whether generation is in progress
 * - isComplete: Whether generation finished successfully
 * - hasError: Whether an error occurred
 */
export function useDashboardAgent() {
  // Use CopilotKit v2's useAgent for AG-UI communication
  const { agent } = useAgent({
    agentId: "dashboard_agent",
  });

  // Get state from agent, with fallback to initial state
  const state = (agent.state as DashboardState) || initialState;

  // Group components by zone for rendering
  const componentsByZone = useMemo(
    () => groupByZone(state.components || []),
    [state.components]
  );

  // Trigger dashboard generation by sending a message to the agent
  const generateDashboard = useCallback(async (markdown: string) => {
    // Update state with markdown content
    agent.setState({
      ...initialState,
      markdown_content: markdown,
      status: "analyzing",
    });

    // Add a user message and run the agent
    agent.addMessage({
      id: crypto.randomUUID(),
      role: "user",
      content: `Please analyze this markdown document and generate a dashboard for it:\n\n${markdown}`,
    });

    // Run the agent
    await agent.runAgent();
  }, [agent]);

  // Stop any running generation
  const stop = useCallback(() => {
    agent.abortRun();
  }, [agent]);

  // Derived state flags
  const isGenerating = agent.isRunning || state.status === "analyzing" || state.status === "generating";
  const isComplete = state.status === "complete";
  const hasError = state.status === "error";

  return {
    state,
    setState: agent.setState.bind(agent),
    componentsByZone,
    generateDashboard,
    stop,
    isGenerating,
    isComplete,
    hasError,
    // Expose agent for advanced use cases
    agent,
  };
}

/**
 * Hook to render agent state in chat/activity UI.
 * Placeholder for future CopilotKit state rendering integration.
 */
export function useDashboardStateRender() {
  return null;
}
