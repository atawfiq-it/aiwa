<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import AgentConfigPanel from './agent/AgentConfigPanel.svelte';
  import VisualDagConsole from './agent/VisualDagConsole.svelte';

  let agents: any[] = [];
  let selectedAgentId = '';
  let promptText = '';
  let requireApproval = false;
  let isRunning = false;
  let currentRunId: string | null = null;
  let dagNodes: any[] = [];
  let finalReport = '';
  let activeApproval: any = null;

  async function loadAgents() {
    const res = await apiFetch('/agents');
    if (res.ok) {
      agents = await res.json();
      if (agents.length > 0 && !selectedAgentId) selectedAgentId = agents[0].id;
    }
  }

  async function launchAgent() {
    if (!promptText.trim() || !selectedAgentId || isRunning) return;
    isRunning = true;
    dagNodes = [];
    finalReport = '';
    currentRunId = null;

    try {
      const response = await apiFetch(`/agents/${selectedAgentId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptText, require_human_approval: requireApproval }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let currentEventType = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        for (const line of chunk.split('\n')) {
          const trimmed = line.trim();

          if (trimmed.startsWith('event: ')) {
            currentEventType = trimmed.slice(7).trim();
            continue;
          }

          if (trimmed.startsWith('data: ')) {
            try {
              const data = JSON.parse(trimmed.slice(6).trim());

              if (currentEventType === 'agent_started' || data.run_id) currentRunId = data.run_id;
              if (currentEventType === 'dag_node' || data.node_id) dagNodes = [...dagNodes, data];
              if (currentEventType === 'approval_required' || (data.tool_name && data.arguments)) activeApproval = data;
              if (currentEventType === 'agent_completed' || data.final_answer) finalReport = data.final_answer;
              if (currentEventType === 'error' || data.error) {
                dagNodes = [...dagNodes, { node_id: 'err', node_type: 'observation', title: 'Error', output: data.error, status: 'failed' }];
              }
            } catch {}
          }
        }
      }
    } finally {
      isRunning = false;
    }
  }

  onMount(loadAgents);
</script>

<div class="flex-1 flex overflow-hidden bg-[var(--bg-base)]">
  <AgentConfigPanel
    {agents}
    bind:selectedAgentId
    bind:promptText
    bind:requireApproval
    {isRunning}
    {currentRunId}
    onLaunch={launchAgent}
  />

  <div class="flex-1 p-8 overflow-y-auto">
    <VisualDagConsole
      {dagNodes}
      {finalReport}
      bind:activeApproval
      onDecision={() => {}}
    />
  </div>
</div>
