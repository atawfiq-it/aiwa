<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import {
    activeModelId,
    currentTheme,
    registeredModels,
    sessionToken,
    supervisorStatus,
    type ThemePalette,
  } from '../../lib/stores';

  let customScanPaths = '';
  let scannedModels: any[] = [];
  let isScanning = false;
  let saveSuccessMessage = '';

  function setTheme(theme: ThemePalette) {
    $currentTheme = theme;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('aiwa_theme', theme);
    }
  }

  async function loadDirectories() {
    try {
      const res = await apiFetch('/models/directories');
      if (res.ok) {
        const dirs = await res.json();
        customScanPaths = dirs.join('\n');
      }
    } catch {}
  }

  async function loadSupervisor() {
    try {
      const res = await apiFetch('/models/status');
      if (res.ok) {
        $supervisorStatus = await res.json();
        $activeModelId = $supervisorStatus.active_model_id || '';
      }
    } catch {}
  }

  async function refreshRegisteredModels() {
    try {
      const res = await apiFetch('/models');
      if (res.ok) {
        $registeredModels = await res.json();
      }
    } catch {}
  }

  async function triggerDeepScan() {
    isScanning = true;
    saveSuccessMessage = '';
    const pathsArray = customScanPaths
      .split('\n')
      .map((p) => p.trim())
      .filter(Boolean);

    try {
      // 1. Save configured paths
      await apiFetch('/models/directories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directories: pathsArray }),
      });

      // 2. Perform deep recursive scan
      const res = await apiFetch('/models/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: pathsArray }),
      });

      if (res.ok) {
        const data = await res.json();
        scannedModels = data.models;
        saveSuccessMessage = `Discovered ${scannedModels.length} models across all folder depths.`;
      }
    } catch (e: any) {
      alert(`Scan failed: ${e.message}`);
    } finally {
      isScanning = false;
    }
  }

  async function registerModel(model: any) {
    try {
      const res = await apiFetch('/models/register-scanned', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: model.display_name,
          file_path: model.file_path,
          mmproj_path: model.mmproj_path,
          context_length: 4096,
          vision_supported: model.vision_supported,
          is_default: false,
        }),
      });

      if (res.ok) {
        await refreshRegisteredModels();
        alert(`Successfully registered '${model.display_name}'!`);
      }
    } catch (e: any) {
      alert(`Registration failed: ${e.message}`);
    }
  }

  async function deleteModel(id: string, name: string) {
    if (!confirm(`Remove model '${name}' from catalog?`)) return;
    try {
      const res = await apiFetch(`/models/${id}`, { method: 'DELETE' });
      if (res.ok) {
        $registeredModels = $registeredModels.filter((m) => m.id !== id);
      }
    } catch (e: any) {
      alert(`Delete failed: ${e.message}`);
    }
  }

  onMount(() => {
    loadDirectories();
    loadSupervisor();
    refreshRegisteredModels();
  });
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-4xl bg-[var(--bg-base)]">
  <!-- Header -->
  <div>
    <h2 class="text-xl font-bold text-[var(--text-main)]">System & Hardware Settings</h2>
    <p class="text-xs text-[var(--text-muted)] mt-1">
      Manage appearance, authentication tokens, hardware resource allocation, and multi-drive model directories.
    </p>
  </div>

  <!-- 1. Appearance / Theme Toggle -->
  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm">
    <div>
      <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Appearance & Theme</h3>
      <p class="text-xs text-[var(--text-muted)] mt-0.5">Switch between clean modern Dark and Light palettes.</p>
    </div>

    <div class="flex items-center gap-3">
      <button
        type="button"
        on:click={() => setTheme('dark')}
        class={`px-5 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2 border transition ${
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
        class={`px-5 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2 border transition ${
          $currentTheme === 'light'
            ? 'bg-blue-600 text-white border-blue-500 shadow-md'
            : 'bg-[var(--bg-base)] text-[var(--text-muted)] border-[var(--border-color)] hover:text-[var(--text-main)]'
        }`}
      >
        ☀️ Light Mode
      </button>
    </div>
  </div>

  <!-- 2. Hardware & VRAM Arbiter Status -->
  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">GPU Memory & Model Supervisor</h3>
        <p class="text-xs text-[var(--text-muted)] mt-0.5">Dynamic hardware arbitration enforcing an 80% safe VRAM ceiling.</p>
      </div>
      <button
        type="button"
        on:click={loadSupervisor}
        class="px-2.5 py-1 text-xs font-medium rounded-lg bg-[var(--bg-base)] border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-main)] transition"
      >
        🔄 Refresh
      </button>
    </div>

    {#if $supervisorStatus}
      <div class="grid grid-cols-3 gap-3 text-xs font-mono">
        <div class="p-3 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl space-y-1">
          <span class="text-[10px] uppercase text-[var(--text-muted)] block font-sans font-semibold">Engine State</span>
          <span class="font-bold text-sm text-[var(--accent)]">{$supervisorStatus.state}</span>
        </div>

        <div class="p-3 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl space-y-1">
          <span class="text-[10px] uppercase text-[var(--text-muted)] block font-sans font-semibold">Active LLM</span>
          <span class="font-bold truncate block text-[var(--text-main)]">
            {$supervisorStatus.active_model_name || 'None'}
          </span>
        </div>

        <div class="p-3 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl space-y-1">
          <span class="text-[10px] uppercase text-[var(--text-muted)] block font-sans font-semibold">VRAM Usage</span>
          {#if $supervisorStatus.vram}
            <span class="font-bold text-[var(--text-main)]">
              {($supervisorStatus.vram.used_mb / 1024).toFixed(1)} / {($supervisorStatus.vram.allowed_ceiling_mb / 1024).toFixed(1)} GB
              <span class="text-[10px] text-[var(--text-muted)] font-normal font-sans">(80% Cap)</span>
            </span>
          {:else}
            <span class="text-slate-500">Unavailable</span>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <!-- 3. Local Authorization Token -->
  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-3 shadow-sm">
    <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Local Authentication Token</h3>
    <p class="text-xs text-[var(--text-muted)]">
      The daemon generates an ephemeral token on boot (persisted at <code class="font-mono text-[var(--text-main)]">data/.aiwa_session_token</code>).
    </p>
    <input
      type="password"
      bind:value={$sessionToken}
      placeholder="Paste session token..."
      class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] text-[var(--text-main)] rounded-xl p-3 text-xs font-mono focus:outline-none focus:border-[var(--accent)]"
    />
  </div>

  <!-- 4. Registered Models Catalog -->
  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Registered Models Catalog</h3>
        <p class="text-xs text-[var(--text-muted)] mt-0.5">Models registered for instant switching in the chat workspace.</p>
      </div>
      <span class="text-xs font-mono text-[var(--text-muted)]">{$registeredModels.length} registered</span>
    </div>

    {#if $registeredModels.length === 0}
      <p class="text-xs text-[var(--text-muted)] italic">No models registered yet. Scan directories below to register your local models.</p>
    {:else}
      <div class="space-y-2">
        {#each $registeredModels as m}
          <div class="p-3 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl flex items-center justify-between text-xs">
            <div class="space-y-0.5 max-w-lg">
              <div class="flex items-center gap-2">
                <span class="font-bold text-[var(--text-main)]">{m.display_name}</span>
                {#if m.vision_supported}
                  <span class="px-2 py-0.5 bg-indigo-900/30 text-indigo-400 border border-indigo-700/40 rounded text-[10px] font-semibold">
                    👁️ Vision Ready
                  </span>
                {/if}
                <span class="text-[10px] font-mono text-[var(--text-muted)]">ctx: {m.context_length}</span>
              </div>
              <p class="font-mono text-[11px] text-[var(--text-muted)] truncate">{m.file_path}</p>
            </div>

            <button
              type="button"
              on:click={() => deleteModel(m.id, m.display_name)}
              class="px-3 py-1 bg-rose-500/10 text-rose-500 hover:bg-rose-500 hover:text-white border border-rose-500/20 rounded-lg text-xs font-medium transition"
              title="Remove model from catalog"
            >
              Remove
            </button>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- 5. Deep Recursive Multi-Directory Scanner -->
  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm">
    <div>
      <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Multi-Drive Model Scanner</h3>
      <p class="text-xs text-[var(--text-muted)] mt-0.5">
        Recursively searches all folder depths for LLM (<code class="font-mono">.gguf</code>), Diffusion (<code class="font-mono">.safetensors</code>), and Voice models.
      </p>
    </div>

    <div class="space-y-2">
      <label for="search-dirs" class="text-xs font-semibold text-[var(--text-main)] block">
        Search Root Directories (one absolute path per line):
      </label>
      <textarea
        id="search-dirs"
        rows="3"
        bind:value={customScanPaths}
        placeholder="/run/media/alpha/.../models&#10;/home/.../weights"
        class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] text-[var(--text-main)] rounded-xl p-3 text-xs font-mono focus:outline-none focus:border-[var(--accent)]"
      ></textarea>
    </div>

    <div class="flex items-center gap-3">
      <button
        type="button"
        on:click={triggerDeepScan}
        disabled={isScanning}
        style="background-color: var(--accent); color: var(--accent-text);"
        class="px-5 py-2.5 disabled:opacity-40 rounded-xl text-xs font-bold transition shadow-sm flex items-center gap-2"
      >
        {#if isScanning}
          <span class="animate-spin">🌀</span> Scanning All Subdirectories...
        {:else}
          🔍 Run Deep Recursive Scan
        {/if}
      </button>

      {#if saveSuccessMessage}
        <span class="text-xs text-[var(--accent)] font-semibold">{saveSuccessMessage}</span>
      {/if}
    </div>

    <!-- Scanned Models Results -->
    {#if scannedModels.length > 0}
      <div class="space-y-2.5 pt-4 border-t border-[var(--border-color)]">
        <h4 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
          Discovered Files on Disk ({scannedModels.length}):
        </h4>
        <div class="space-y-2 max-h-80 overflow-y-auto">
          {#each scannedModels as model}
            <div class="p-3 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl flex items-center justify-between text-xs">
              <div class="space-y-0.5 max-w-lg">
                <div class="flex items-center gap-2">
                  <span class={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                    model.category === 'llm'
                      ? 'bg-indigo-950 text-indigo-300 border border-indigo-700/50'
                      : model.category === 'diffusion'
                      ? 'bg-purple-950 text-purple-300 border border-purple-700/50'
                      : 'bg-emerald-950 text-emerald-300 border border-emerald-700/50'
                  }`}>
                    {model.category}
                  </span>
                  <span class="font-bold text-[var(--text-main)]">{model.display_name}</span>
                  {#if model.vision_supported}
                    <span class="text-indigo-400 font-semibold text-[11px]">👁️ Vision</span>
                  {/if}
                </div>
                <p class="font-mono text-[11px] text-[var(--text-muted)] truncate">{model.file_path}</p>
                <p class="text-[10px] text-[var(--text-muted)]">
                  {model.file_size_gb} GB • {model.quantization || 'standard'}
                </p>
              </div>

              {#if model.category === 'llm'}
                <button
                  type="button"
                  on:click={() => registerModel(model)}
                  class="px-3 py-1.5 bg-[var(--bg-card)] hover:opacity-80 border border-[var(--border-color)] text-[var(--text-main)] rounded-lg text-xs font-semibold transition"
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
</div>
