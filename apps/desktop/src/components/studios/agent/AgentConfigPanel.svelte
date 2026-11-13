<script lang="ts">
  import { supervisorStatus } from '../../../lib/stores';
  import SandboxFileExplorer from './SandboxFileExplorer.svelte';

  export let agents: any[] = [];
  export let selectedAgentId: string = '';
  export let promptText: string = '';
  export let requireApproval: boolean = false;
  export let isRunning: boolean = false;
  export let currentRunId: string | null = null;
  export let onLaunch: () => void;

  $: activeAgent = agents.find((a) => a.id === selectedAgentId);
</script>

<div class="w-96 border-r border-[var(--border-color)] p-6 flex flex-col justify-between overflow-y-auto space-y-6 bg-[var(--bg-card)] select-none shrink-0 shadow-sm">
  <div class="space-y-4">
    <div>
      <h2 class="text-base font-bold text-[var(--text-main)]">🤖 Agent Studio Pro</h2>
      <p class="text-[11px] text-[var(--text-muted)]">Visual DAG reasoning, sandbox breakpoints & tool calling.</p>
    </div>

    <!-- Agent Dropdown -->
    <div>
      <label for="agent-picker" class="text-xs font-semibold text-[var(--text-muted)] block mb-1">Scenario Agent:</label>
      <select
        id="agent-picker"
        bind:value={selectedAgentId}
        class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2.5 text-xs text-[var(--text-main)] font-semibold focus:outline-none"
      >
        {#each agents as a}
          <option value={a.id}>{a.name}</option>
        {/each}
      </select>
    </div>

    <!-- Agent Description & Tools Badge -->
    {#if activeAgent}
      <div class="p-3 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl space-y-1.5 text-xs">
        <p class="text-[11px] text-[var(--text-muted)] leading-relaxed">{activeAgent.description}</p>
        <div class="flex items-center gap-1.5 pt-1 border-t border-[var(--border-color)] text-[10px]">
          <span class="text-[var(--text-muted)] font-medium">Tools:</span>
          <span class="font-mono text-indigo-400 font-bold">{activeAgent.tools_json}</span>
        </div>
      </div>
    {/if}

    <!-- Human Breakpoint Toggle -->
    <label class="flex items-center gap-2 text-xs text-[var(--text-main)] cursor-pointer select-none">
      <input type="checkbox" bind:checked={requireApproval} class="rounded accent-indigo-600 cursor-pointer" />
      <span>Pause for Approval before Code Execution (HITL)</span>
    </label>

    <!-- Task Prompt Textarea -->
    <div>
      <label for="task-prompt" class="text-xs font-semibold text-[var(--text-muted)] block mb-1">Task Assignment / Code to Review:</label>
      <textarea
        id="task-prompt"
        rows="5"
        bind:value={promptText}
        placeholder="Describe task or paste Python code to audit..."
        class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-3 text-xs font-mono text-[var(--text-main)] focus:outline-none focus:border-[var(--accent)]"
      ></textarea>
    </div>

    <!-- Workspace File Explorer -->
    <SandboxFileExplorer activeRunId={currentRunId} />
  </div>

  <!-- Launch Button -->
  <button
    type="button"
    on:click={onLaunch}
    disabled={isRunning || !promptText.trim() || $supervisorStatus?.state !== 'Ready'}
    class="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-xs font-bold text-white rounded-xl shadow-md transition flex items-center justify-center gap-2"
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
