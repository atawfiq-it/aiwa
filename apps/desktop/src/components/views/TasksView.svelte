<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';

  let tasks: any[] = [];

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

<div class="flex-1 p-8 overflow-y-auto space-y-6 max-w-5xl">
  <div>
    <h2 class="text-xl font-bold text-slate-100">Task Queue & Subprocess Operations</h2>
    <p class="text-xs text-slate-400 mt-1">Real-time status of asynchronous background tasks, ComfyUI diffusion jobs, and downloads.</p>
  </div>

  <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
    <table class="w-full text-left text-xs border-collapse">
      <thead>
        <tr class="border-b border-slate-800 text-slate-400 bg-slate-950/40">
          <th class="p-3">Task ID</th>
          <th class="p-3">Type</th>
          <th class="p-3">Status</th>
          <th class="p-3">Created</th>
        </tr>
      </thead>
      <tbody>
        {#each tasks as t}
          <tr class="border-b border-slate-800/40">
            <td class="p-3 font-mono text-slate-500">{t.id.slice(0, 8)}</td>
            <td class="p-3 font-semibold text-slate-300">{t.task_type}</td>
            <td class="p-3">
              <span class={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                t.status === 'completed'
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  : t.status === 'running'
                  ? 'bg-indigo-950 text-indigo-400 border border-indigo-800 animate-pulse'
                  : 'bg-slate-800 text-slate-400'
              }`}>{t.status}</span>
            </td>
            <td class="p-3 text-slate-500">{new Date(t.created_at).toLocaleTimeString()}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>
