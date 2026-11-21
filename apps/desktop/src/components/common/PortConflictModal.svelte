<script lang="ts">
  import { apiFetch } from '../../lib/api';

  export let conflict: {
    port: number;
    service_name: string;
    owner: { pid: number | null; name: string; cmdline: string };
    model_id?: string;
  } | null = null;
  export let onResolved: (retry: boolean) => void;

  let isWorking = false;

  async function resolve(action: 'kill' | 'switch' | 'abort') {
    if (!conflict || isWorking) return;
    isWorking = true;
    try {
      const res = await apiFetch('/system/port-resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          port: conflict.port,
          pid: conflict.owner.pid,
          service_type: conflict.service_name.includes('ComfyUI') ? 'comfyui' : 'llm',
          action,
        }),
      });

      if (res.ok) {
        conflict = null;
        onResolved(action !== 'abort');
      } else {
        const err = await res.json();
        alert(`Failed resolving port conflict: ${err.detail}`);
      }
    } finally {
      isWorking = false;
    }
  }
</script>

{#if conflict}
  <div class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 select-none">
    <div class="bg-[var(--bg-card)] border-2 border-amber-500/60 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center gap-2 text-amber-400 font-bold text-base">
        <span>⚠️</span>
        <span>Port {conflict.port} In Use</span>
      </div>

      <p class="text-xs text-[var(--text-main)] leading-relaxed">
        <strong>{conflict.service_name}</strong> needs port <span class="font-mono text-indigo-400">{conflict.port}</span>,
        which is currently claimed by another application:
      </p>

      <div class="p-3 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl text-xs font-mono space-y-1">
        <div><span class="text-[var(--text-muted)]">Process:</span> <strong class="text-[var(--text-main)]">{conflict.owner.name}</strong></div>
        <div><span class="text-[var(--text-muted)]">PID:</span> {conflict.owner.pid || 'Unknown'}</div>
        <div class="truncate text-[10px] text-[var(--text-muted)]">{conflict.owner.cmdline}</div>
      </div>

      <div class="flex flex-col gap-2 pt-2">
        {#if conflict.owner.pid}
          <button
            type="button"
            disabled={isWorking}
            on:click={() => resolve('kill')}
            class="w-full py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-xl transition shadow"
          >
            Close '{conflict.owner.name}' & Reclaim Port {conflict.port}
          </button>
        {/if}

        <button
          type="button"
          disabled={isWorking}
          on:click={() => resolve('switch')}
          class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition shadow"
        >
          Switch to Another Free Port Automatically
        </button>

        <button
          type="button"
          disabled={isWorking}
          on:click={() => resolve('abort')}
          class="w-full py-2 bg-[var(--bg-base)] hover:opacity-80 border border-[var(--border-color)] text-[var(--text-muted)] text-xs font-semibold rounded-xl transition"
        >
          Terminate Action
        </button>
      </div>
    </div>
  </div>
{/if}
