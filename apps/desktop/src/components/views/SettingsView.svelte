<script lang="ts">
  import { apiFetch } from '../../lib/api';
  import { registeredModels, sessionToken } from '../../lib/stores';

  let customScanPaths = '';
  let scannedModels: any[] = [];
  let isScanning = false;

  async function scan() {
    isScanning = true;
    const paths = customScanPaths.split('\n').map((p) => p.trim()).filter(Boolean);
    const res = await apiFetch('/models/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths }),
    });
    if (res.ok) scannedModels = (await res.json()).models;
    isScanning = false;
  }

  async function register(m: any) {
    const res = await apiFetch('/models/register-scanned', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: m.display_name, file_path: m.file_path, mmproj_path: m.mmproj_path, vision_supported: m.vision_supported, context_length: 4096 }),
    });
    if (res.ok) alert(`Registered ${m.display_name}!`);
  }
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-6 max-w-4xl">
  <div>
    <h2 class="text-xl font-bold">Model Scanner & System Settings</h2>
    <p class="text-xs text-slate-400 mt-1">Deep recursive scanner for LLM, Diffusion, and Voice models.</p>
  </div>

  <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
    <label class="text-xs font-semibold text-slate-300 block">Session Token:</label>
    <input type="password" bind:value={$sessionToken} class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-xs font-mono" />

    <label class="text-xs font-semibold text-slate-300 block mt-4">Search Directories (one per line):</label>
    <textarea rows="3" bind:value={customScanPaths} placeholder="/path/to/models" class="w-full bg-slate-800 border border-slate-700 rounded p-3 text-xs font-mono"></textarea>

    <button on:click={scan} disabled={isScanning} class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold rounded-lg">
      {isScanning ? 'Scanning All Sub-directories...' : '🔍 Run Recursive Scan'}
    </button>
  </div>

  {#if scannedModels.length > 0}
    <div class="space-y-2">
      {#each scannedModels as model}
        <div class="bg-slate-900 border border-slate-800 p-3 rounded-lg flex items-center justify-between text-xs">
          <div>
            <span class="font-bold text-slate-200">{model.display_name}</span>
            <span class="ml-2 text-slate-400">({model.category} • {model.file_size_gb} GB)</span>
            <p class="text-[11px] font-mono text-slate-500 truncate max-w-md">{model.file_path}</p>
          </div>
          {#if model.category === 'llm'}
            <button on:click={() => register(model)} class="px-3 py-1 bg-slate-800 hover:bg-indigo-600 rounded">+ Register</button>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
