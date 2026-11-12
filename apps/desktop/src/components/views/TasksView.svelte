<!-- In apps/desktop/src/components/views/TasksView.svelte: -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';

  let tasks: any[] = [];

  const taskTypeLabels: Record<string, string> = {
    hf_model_download: 'Model Download (Hub)',
    image_generation: 'Image Generation (Diffusion)',
    audio_transcription: 'Speech-to-Text (Whisper)',
    text_to_speech: 'Voice Synthesis (Kokoro)',
    pdf_extraction: 'Document Parsing (PyMuPDF)',
    llm_summarize: 'Executive Summary (LLM)',
  };

  function formatTaskType(raw: string): string {
    return taskTypeLabels[raw] || raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function formatDateTime(isoString: string): string {
    if (!isoString) return '-';
    const d = new Date(isoString);
    return d.toLocaleString([], {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  async function loadTasks() {
    const res = await apiFetch('/tasks');
    if (res.ok) tasks = await res.json();
  }

  onMount(() => {
    loadTasks();
    const interval = setInterval(loadTasks, 2500);
    return () => clearInterval(interval);
  });
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-6 max-w-6xl">
  <div>
    <h2 class="text-xl font-bold text-[var(--text-main)]">Task Queue & Process Operations</h2>
    <p class="text-xs text-[var(--text-muted)] mt-1">Real-time status of background diffusion renders, audio jobs, and model downloads.</p>
  </div>

  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl overflow-hidden shadow-sm">
    <table class="w-full text-left text-xs border-collapse">
      <thead>
        <tr class="border-b border-[var(--border-color)] text-[var(--text-muted)] bg-[var(--bg-base)]">
          <th class="p-3.5 font-bold uppercase tracking-wider text-[10px]">Task ID</th>
          <th class="p-3.5 font-bold uppercase tracking-wider text-[10px]">Operation Type</th>
          <th class="p-3.5 font-bold uppercase tracking-wider text-[10px]">Status</th>
          <th class="p-3.5 font-bold uppercase tracking-wider text-[10px]">Created Date & Time</th>
        </tr>
      </thead>
      <tbody>
        {#if tasks.length === 0}
          <tr>
            <td colspan="4" class="p-6 text-center text-[var(--text-muted)]">No background tasks found.</td>
          </tr>
        {:else}
          {#each tasks as t}
            <tr class="border-b border-[var(--border-color)]/60 hover:bg-[var(--bg-base)]/50 transition">
              <td class="p-3.5 font-mono text-[var(--text-muted)]">{t.id.slice(0, 8)}</td>
              <td class="p-3.5 font-semibold text-[var(--text-main)]">{formatTaskType(t.task_type)}</td>
              <td class="p-3.5">
                <span class={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                  t.status === 'completed'
                    ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/30'
                    : t.status === 'running'
                    ? 'bg-indigo-500/10 text-indigo-500 border border-indigo-500/30 animate-pulse'
                    : t.status === 'failed'
                    ? 'bg-rose-500/10 text-rose-500 border border-rose-500/30'
                    : 'bg-slate-500/10 text-slate-400 border border-slate-500/30'
                }`}>{t.status}</span>
              </td>
              <td class="p-3.5 font-mono text-[var(--text-muted)]">{formatDateTime(t.created_at)}</td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</div>
