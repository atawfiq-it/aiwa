<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import SandboxFileExplorer from './agent/SandboxFileExplorer.svelte';
  import VisualDagConsole from './agent/VisualDagConsole.svelte';
  import { supervisorStatus } from '../../lib/stores';

  let agents: any[] = [];
  let selectedAgentId = '';
  let promptText = '';
  let requireApproval = false;
  let isRunning = false;
  let currentRunId: string | null = null;
  let dagNodes: any[] = [];
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

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        for (const line of decoder.decode(value).split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6).trim());

              if (line.includes('agent_started')) {
                currentRunId = data.run_id;
              } else if (line.includes('dag_node')) {
                dagNodes = [...dagNodes, data];
              } else if (line.includes('approval_required')) {
                activeApproval = data;
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
  <!-- Left Config Panel -->
  <div class="w-96 border-r border-[var(--border-color)] p-6 flex flex-col justify-between overflow-y-auto space-y-6 bg-[var(--bg-card)]">
    <div class="space-y-4">
      <div>
        <h2 class="text-base font-bold text-[var(--text-main)]">🤖 Agent Studio Pro</h2>
        <p class="text-[11px] text-[var(--text-muted)]">Visual DAG reasoning, sandbox breakpoints & tool calling.</p>
      </div>

      <div>
        <label for="agent-picker" class="text-xs font-semibold text-[var(--text-muted)] block mb-1">Scenario Agent:</label>
        <select id="agent-picker" bind:value={selectedAgentId} class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2.5 text-xs text-[var(--text-main)] font-semibold">
          {#each agents as a}
            <option value={a.id}>{a.name}</option>
          {/each}
        </select>
      </div>

      <!-- Human Breakpoint Switch -->
      <label class="flex items-center gap-2 text-xs text-[var(--text-main)] cursor-pointer select-none">
        <input type="checkbox" bind:checked={requireApproval} class="rounded accent-indigo-600" />
        <span>Pause for Approval before Code Execution (HITL)</span>
      </label>

      <!-- Task Prompt -->
      <div>
        <label for="task-prompt" class="text-xs font-semibold text-[var(--text-muted)] block mb-1">Task Assignment:</label>
        <textarea id="task-prompt" rows="5" bind:value={promptText} placeholder="Describe task or paste Python code to audit..." class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-3 text-xs font-mono text-[var(--text-main)]"></textarea>
      </div>

      <SandboxFileExplorer activeRunId={currentRunId} />
    </div>

    <button
      on:click={launchAgent}
      disabled={isRunning || !promptText.trim() || $supervisorStatus?.state !== 'Ready'}
      class="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-xs font-bold text-white rounded-xl shadow-md transition"
    >
      {#if $supervisorStatus?.state !== 'Ready'}
        ⚠️ Load Model in Header First
      {:else if isRunning}
        <span class="animate-spin">🌀</span> Agent Reasoning...
      {:else}
        🚀 Launch Autonomous Agent
      {/if}
    </button>
  </div>

  <!-- Right Visual DAG Console -->
  <div class="flex-1 p-8 overflow-y-auto">
    <VisualDagConsole {dagNodes} bind:activeApproval onDecision={() => {}} />
  </div>
</div>
