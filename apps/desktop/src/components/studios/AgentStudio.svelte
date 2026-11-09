<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';

  let agents: any[] = [];
  let selectedAgentId = '';
  let promptText = '';
  let isRunning = false;
  let executionSteps: { type: string; title: string; content: string }[] = [];
  let finalReport = '';

  async function loadAgents() {
    const res = await apiFetch('/agents');
    if (res.ok) {
      agents = await res.json();
      if (agents.length > 0 && !selectedAgentId) {
        selectedAgentId = agents[0].id;
      }
    }
  }

  async function launchAgent() {
    if (!promptText.trim() || !selectedAgentId || isRunning) return;
    isRunning = true;
    executionSteps = [];
    finalReport = '';

    const selectedAgent = agents.find((a) => a.id === selectedAgentId);
    executionSteps = [{ type: 'info', title: 'Agent Initialized', content: `Started ${selectedAgent?.name}...` }];

    try {
      const response = await apiFetch(`/agents/${selectedAgentId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptText, max_iterations: 5 }),
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

              if (line.includes('tool_call_started')) {
                executionSteps = [
                  ...executionSteps,
                  {
                    type: 'tool_call',
                    title: `Invoking Tool: ${data.tool}`,
                    content: JSON.stringify(data.arguments, null, 2),
                  },
                ];
              } else if (line.includes('tool_call_completed')) {
                executionSteps = [
                  ...executionSteps,
                  {
                    type: 'tool_result',
                    title: `Tool Output (${data.tool})`,
                    content: typeof data.output === 'string' ? data.output : JSON.stringify(data.output, null, 2),
                  },
                ];
              } else if (data.final_answer) {
                finalReport = data.final_answer;
              } else if (data.error) {
                executionSteps = [...executionSteps, { type: 'error', title: 'Execution Error', content: data.error }];
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

<div class="flex-1 flex overflow-hidden bg-slate-900">
  <!-- Left Agent Config Panel -->
  <div class="w-96 border-r border-slate-800 p-6 flex flex-col justify-between overflow-y-auto space-y-6">
    <div class="space-y-4">
      <div>
        <h2 class="text-base font-bold text-slate-100">🤖 Autonomous Agent Studio</h2>
        <p class="text-[11px] text-slate-400">Autonomous tool execution with Python sandbox & LanceDB.</p>
      </div>

      <!-- Agent Selector -->
      <div>
        <label for="agent-select" class="text-xs font-semibold text-slate-300 block mb-1">Select Scenario Agent:</label>
        <select
          id="agent-select"
          bind:value={selectedAgentId}
          class="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-semibold"
        >
          {#each agents as a}
            <option value={a.id}>{a.name}</option>
          {/each}
        </select>
      </div>

      <!-- Selected Agent Info Card -->
      {#if selectedAgentId}
        {@const activeAgent = agents.find((a) => a.id === selectedAgentId)}
        <div class="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-2 text-xs">
          <p class="text-slate-400 text-[11px]">{activeAgent?.description}</p>
          <div class="flex items-center gap-1.5 pt-1 border-t border-slate-800/80">
            <span class="text-slate-500 text-[10px]">Bound Tools:</span>
            <span class="font-mono text-indigo-400 text-[10px]">{activeAgent?.tools_json}</span>
          </div>
        </div>
      {/if}

      <!-- Task Prompt -->
      <div>
        <label for="agent-prompt" class="text-xs font-semibold text-slate-300 block mb-1">Task Assignment / Code to Review:</label>
        <textarea
          id="agent-prompt"
          rows="5"
          bind:value={promptText}
          placeholder="e.g. Audit this Python function and test its speed:&#10;def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)"
          class="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
        ></textarea>
      </div>
    </div>

    <button
      on:click={launchAgent}
      disabled={isRunning || !promptText.trim()}
      class="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white rounded-xl transition shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
    >
      {#if isRunning}
        <span class="animate-spin">🌀</span> Agent Executing Tools...
      {:else}
        🚀 Launch Autonomous Agent
      {/if}
    </button>
  </div>

  <!-- Execution Console & Report (Right) -->
  <div class="flex-1 flex flex-col justify-between p-8 overflow-y-auto space-y-6">
    <div>
      <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Live Execution Steps & Tool Calls</h3>

      {#if executionSteps.length === 0}
        <div class="border-2 border-dashed border-slate-800 rounded-2xl p-12 text-center text-slate-500 space-y-2">
          <span class="text-3xl">⚙️</span>
          <p class="text-sm font-medium">Console Idle</p>
          <p class="text-xs text-slate-600">Select an agent scenario and launch an assignment.</p>
        </div>
      {:else}
        <div class="space-y-3 font-mono text-xs">
          {#each executionSteps as step}
            <div class={`p-3.5 rounded-xl border ${
              step.type === 'tool_call'
                ? 'bg-indigo-950/20 border-indigo-500/50 text-indigo-300'
                : step.type === 'tool_result'
                ? 'bg-slate-950 border-slate-800 text-emerald-400'
                : 'bg-slate-900 border-slate-800 text-slate-300'
            }`}>
              <div class="font-bold flex items-center gap-2 mb-1.5">
                <span>{step.type === 'tool_call' ? '⚡' : step.type === 'tool_result' ? '📦' : 'ℹ️'}</span>
                <span>{step.title}</span>
              </div>
              <pre class="whitespace-pre-wrap text-[11px] overflow-x-auto text-slate-300 p-2 bg-black/30 rounded-lg">{step.content}</pre>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Final Synthesized Report -->
    {#if finalReport}
      <div class="mt-8 bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-3">
        <div class="flex items-center gap-2 text-xs font-bold text-indigo-400 uppercase tracking-wider">
          <span>📋</span> Agent Final Synthesis & Audit Report
        </div>
        <div class="text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
          {finalReport}
        </div>
      </div>
    {/if}
  </div>
</div>
