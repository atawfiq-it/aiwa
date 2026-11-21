<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import {
    currentTheme,
    registeredModels,
    sessionToken,
  } from '../../lib/stores';

  let customScanPaths = '';
  let scannedModels: any[] = [];
  let isScanning = false;
  let hardwareProfile: any = null;

  function setTheme(theme: 'dark' | 'light') {
    currentTheme.set(theme);
    localStorage.setItem('aiwa_theme', theme);
  }

  async function loadHardwareAndDirectories() {
    try {
      const [hwRes, dirRes] = await Promise.all([
        apiFetch('/models/hardware'),
        apiFetch('/models/directories'),
      ]);

      if (hwRes.ok) {
        hardwareProfile = await hwRes.json();
      }
      if (dirRes.ok) {
        const dirs = await dirRes.json();
        customScanPaths = dirs.join('\n');
      }
    } catch {}
  }

  async function scan() {
    isScanning = true;
    const paths = customScanPaths
      .split('\n')
      .map((p) => p.trim())
      .filter(Boolean);

    try {
      // 1. Save configured directories
      await apiFetch('/models/directories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directories: paths }),
      });

      // 2. Execute recursive scan
      const res = await apiFetch('/models/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths }),
      });
      if (res.ok) {
        const data = await res.json();
        scannedModels = data.models || [];
      }
    } catch (e: any) {
      alert(`Scan failed: ${e.message}`);
    } finally {
      isScanning = false;
    }
  }

  async function register(m: any) {
    try {
      const res = await apiFetch('/models/register-scanned', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: m.display_name,
          file_path: m.file_path,
          format: m.format || 'gguf',
          mmproj_path: m.mmproj_path,
          vision_supported: m.vision_supported,
          context_length: 4096,
        }),
      });

      if (res.ok) {
        // Refresh global registeredModels store so dropdown updates immediately
        const modelsRes = await apiFetch('/models');
        if (modelsRes.ok) {
          registeredModels.set(await modelsRes.json());
        }
        alert(`Registered '${m.display_name}' successfully!`);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Registration error: ${err.detail || 'Unknown error'}`);
      }
    } catch (e: any) {
      alert(`Network error: ${e.message}`);
    }
  }

  onMount(loadHardwareAndDirectories);
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-6 max-w-5xl bg-[var(--bg-base)]">
  <div>
    <h2 class="text-xl font-bold text-[var(--text-main)]">⚙️ System Settings & Model Catalog</h2>
    <p class="text-xs text-[var(--text-muted)] mt-1">Configure workspace appearance, monitor hardware acceleration, and manage multi-drive model folders.</p>
  </div>

  <!-- 1. Appearance & Theme Switcher -->
  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-3 shadow-sm">
    <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Appearance & Theme</h3>
    <div class="flex items-center gap-3">
      <button
        type="button"
        on:click={() => setTheme('dark')}
        class={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 border transition ${
          $currentTheme === 'dark'
            ? 'bg-indigo-600 text-white border-indigo-500 shadow-md'
            : 'bg-[var(--bg-base)] text-[var(--text-muted)] border-[var(--border-color)] hover:text-[var(--text-main)]'
        }`}
      >
        🌙 Dark Mode
      </button>
      <button
        type="button"
        on:click={() => setTheme('light')}
        class={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 border transition ${
          $currentTheme === 'light'
            ? 'bg-blue-600 text-white border-blue-500 shadow-md'
            : 'bg-[var(--bg-base)] text-[var(--text-muted)] border-[var(--border-color)] hover:text-[var(--text-main)]'
        }`}
      >
        ☀️ Light Mode
      </button>
    </div>
  </div>

  <!-- 2. Hardware Acceleration & VRAM Arbiter Telemetry -->
  {#if hardwareProfile}
    <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-3 shadow-sm">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Hardware Acceleration & Memory Arbiter</h3>
        <span class="px-2.5 py-0.5 bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 rounded-full text-[10px] font-mono font-bold uppercase">
          {hardwareProfile.hardware.backend}
        </span>
      </div>

      <div class="grid grid-cols-3 gap-4 text-xs pt-1">
        <div class="p-3 bg-[var(--bg-base)] rounded-xl border border-[var(--border-color)]">
          <span class="text-[10px] text-[var(--text-muted)] block">Active Device</span>
          <span class="font-bold text-[var(--text-main)]">{hardwareProfile.hardware.device_name}</span>
        </div>
        <div class="p-3 bg-[var(--bg-base)] rounded-xl border border-[var(--border-color)]">
          <span class="text-[10px] text-[var(--text-muted)] block">Memory Ceiling ({hardwareProfile.vram.max_usage_percent}%)</span>
          <span class="font-mono font-bold text-[var(--text-main)]">
            {(hardwareProfile.vram.used_mb / 1024).toFixed(1)} / {(hardwareProfile.vram.allowed_ceiling_mb / 1024).toFixed(1)} GB
          </span>
        </div>
        <div class="p-3 bg-[var(--bg-base)] rounded-xl border border-[var(--border-color)]">
          <span class="text-[10px] text-[var(--text-muted)] block">CPU SIMD Extensions</span>
          <span class="font-mono font-bold text-[var(--text-main)]">{hardwareProfile.hardware.cpu_simd.join(', ')}</span>
        </div>
      </div>
    </div>
  {/if}

  <!-- 3. Authentication & Deep Recursive Scanner -->
  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm">
    <div>
      <label for="session-token-input" class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block mb-1.5">
        Local Daemon Session Token
      </label>
      <input
        id="session-token-input"
        type="password"
        bind:value={$sessionToken}
        placeholder="Auto-synced in dev mode..."
        class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2.5 text-xs font-mono text-[var(--text-main)] focus:outline-none focus:border-[var(--accent)]"
      />
    </div>

    <div class="pt-2 border-t border-[var(--border-color)]">
      <label for="scan-dirs-input" class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block mb-1.5">
        Model Search Root Directories (One Path Per Line)
      </label>
      <textarea
        id="scan-dirs-input"
        rows="3"
        bind:value={customScanPaths}
        placeholder="/path/to/models"
        class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-3 text-xs font-mono text-[var(--text-main)] focus:outline-none focus:border-[var(--accent)]"
      ></textarea>

      <button
        type="button"
        on:click={scan}
        disabled={isScanning}
        class="mt-3 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-sm transition"
      >
        {isScanning ? 'Scanning All Sub-directories...' : '🔍 Run Deep Recursive Scan'}
      </button>
    </div>
  </div>

  <!-- 4. Discovered Models Results -->
  {#if scannedModels.length > 0}
    <div class="space-y-3">
      <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
        Cataloged Models ({scannedModels.length})
      </h3>
      <div class="space-y-2">
        {#each scannedModels as model}
          <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 rounded-xl flex items-center justify-between text-xs shadow-sm">
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                  model.category === 'llm'
                    ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/30'
                    : model.category === 'diffusion'
                    ? 'bg-purple-500/10 text-purple-400 border border-purple-500/30'
                    : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                }`}>
                  {model.category}
                </span>

                {#if model.format}
                  <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--bg-base)] border border-[var(--border-color)] text-[var(--text-muted)] uppercase">
                    {model.format}
                  </span>
                {/if}

                <span class="font-bold text-sm text-[var(--text-main)]">{model.display_name}</span>

                {#if model.vision_supported}
                  <span class="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 rounded text-[10px] font-semibold">👁️ Vision</span>
                {/if}
              </div>

              <p class="text-[11px] font-mono text-[var(--text-muted)] truncate max-w-xl">{model.file_path}</p>
              <p class="text-[10px] text-slate-500">Size: {model.file_size_gb} GB • {model.quantization || 'Standard'}</p>
            </div>

            {#if model.category === 'llm'}
              <button
                type="button"
                on:click={() => register(model)}
                class="px-4 py-2 bg-[var(--bg-base)] hover:bg-indigo-600 hover:text-white border border-[var(--border-color)] hover:border-indigo-500 text-[var(--text-main)] rounded-xl text-xs font-semibold transition"
              >
                + Register
              </button>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>
