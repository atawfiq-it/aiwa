<script lang="ts">
  import { marked } from 'marked';
  import { apiFetch } from '../../../lib/api';

  export let dagNodes: {
    node_id: string;
    node_type: 'goal' | 'planning' | 'tool_call' | 'observation' | 'synthesis';
    title: string;
    content?: string;
    output?: any;
    arguments?: any;
    duration_ms?: number;
    status: string;
  }[] = [];
  export let finalReport: string = '';
  export let activeApproval: { run_id: string; tool_name: string; arguments: any } | null = null;
  export let onDecision: () => void;

  let editedCode = '';

  $: if (activeApproval && activeApproval.arguments?.code) {
    editedCode = activeApproval.arguments.code;
  }

  async function sendDecision(action: 'approve' | 'reject', modified: boolean = false) {
    if (!activeApproval) return;
    const body: any = { action };
    if (modified && editedCode) {
      body.modified_args = { ...activeApproval.arguments, code: editedCode };
    }

    await apiFetch(`/agents/runs/${activeApproval.run_id}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    activeApproval = null;
    onDecision();
  }
</script>

<div class="space-y-6">
  <!-- Human-in-the-Loop Breakpoint Modal -->
  {#if activeApproval}
    <div class="bg-amber-500/10 border-2 border-amber-500 rounded-2xl p-6 shadow-xl space-y-4 select-none">
      <div class="flex items-center gap-2 text-amber-400 font-bold text-sm">
        <span>⚠️</span>
        <span>Human Breakpoint: Inspection Required before Execution</span>
      </div>
      <p class="text-xs text-[var(--text-muted)]">
        The agent requested to execute <strong class="text-[var(--text-main)] font-mono">{activeApproval.tool_name}</strong>. Inspect or modify the code below before proceeding:
      </p>

      <textarea
        rows="5"
        bind:value={editedCode}
        class="w-full bg-[var(--bg-base)] border border-amber-500/40 rounded-xl p-3 text-xs font-mono text-[var(--text-main)] focus:outline-none"
      ></textarea>

      <div class="flex gap-2 justify-end">
        <button
          type="button"
          on:click={() => sendDecision('reject')}
          class="px-4 py-2 bg-rose-500/20 text-rose-400 border border-rose-500/40 rounded-xl text-xs font-bold hover:bg-rose-500/30 transition"
        >
          🛑 Reject
        </button>
        <button
          type="button"
          on:click={() => sendDecision('approve', true)}
          class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-xl text-xs font-bold transition shadow"
        >
          ✏️ Run with Modifications
        </button>
        <button
          type="button"
          on:click={() => sendDecision('approve', false)}
          class="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition shadow"
        >
          ✅ Approve Execution
        </button>
      </div>
    </div>
  {/if}

  <!-- Visual DAG Node Timeline -->
  {#if dagNodes.length === 0}
    <div class="border-2 border-dashed border-[var(--border-color)] rounded-2xl p-12 text-center text-[var(--text-muted)] space-y-2 select-none">
      <span class="text-3xl">⚙️</span>
      <p class="text-sm font-medium text-[var(--text-main)]">Cognitive Reasoning Console Idle</p>
      <p class="text-xs">Select an agent scenario, assign a task, and click Launch to view step nodes.</p>
    </div>
  {:else}
    <div class="space-y-3 font-mono text-xs">
      <div class="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">
        Cognitive Flow & Tool Executions ({dagNodes.length} steps)
      </div>

      <!-- Filter out any legacy synthesis nodes so final answer is never duplicated -->
      {#each dagNodes.filter((n) => n.node_type !== 'synthesis') as node}
        <div class={`p-4 rounded-2xl border transition shadow-sm ${
          node.node_type === 'goal'
            ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
            : node.node_type === 'planning'
            ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400'
            : node.node_type === 'tool_call'
            ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
            : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
        }`}>
          <div class="flex items-center justify-between pb-1.5 border-b border-[var(--border-color)]/60">
            <div class="flex items-center gap-2">
              <span class="font-bold text-[var(--text-main)]">{node.title}</span>
            </div>
            {#if node.duration_ms}
              <span class="text-[10px] text-[var(--text-muted)] font-mono">{node.duration_ms}ms</span>
            {/if}
          </div>

          <div class="mt-2 text-[11px] overflow-x-auto text-[var(--text-main)] whitespace-pre-wrap">
            {#if node.arguments}
              <pre class="p-2.5 bg-[var(--bg-base)] rounded-xl text-amber-300 font-mono">{JSON.stringify(node.arguments, null, 2)}</pre>
            {:else if node.output}
              <pre class="p-2.5 bg-[var(--bg-base)] rounded-xl text-emerald-400 font-mono">{typeof node.output === 'string' ? node.output : JSON.stringify(node.output, null, 2)}</pre>
            {:else}
              <div class="p-2 bg-[var(--bg-base)] rounded-xl text-[var(--text-main)]">{node.content}</div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Single Rendered Markdown Final Report -->
  {#if finalReport}
    <div class="bg-[var(--bg-card)] border-2 border-indigo-500/40 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="flex items-center gap-2 text-xs font-bold text-indigo-400 uppercase tracking-wider">
        <span>📋</span> Agent Final Synthesis & Audit Report
      </div>
      <div class="prose prose-sm max-w-none text-[var(--text-main)] prose-pre:bg-[var(--bg-base)]">
        {@html marked.parse(finalReport)}
      </div>
    </div>
  {/if}
</div>
