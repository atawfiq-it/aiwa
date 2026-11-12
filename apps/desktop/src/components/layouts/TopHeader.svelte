<script lang="ts">
  import { currentTab } from '../../lib/stores';
</script>

<header class="h-14 bg-[var(--bg-card)] border-b border-[var(--border-color)] px-6 flex items-center justify-between select-none shadow-sm shrink-0">
  <!-- Brand -->
  <div class="flex items-center gap-3">
    <div
      style="background-color: var(--accent); color: var(--accent-text);"
      class="h-8 w-8 rounded-lg flex items-center justify-center font-black text-sm shadow-sm"
    >
      A
    </div>
    <span class="font-bold text-sm tracking-tight text-[var(--text-main)]">AIWA Workstation</span>
  </div>

  <!-- 4 Prominent Content Studios -->
  <div class="flex items-center gap-1.5 bg-[var(--bg-base)] p-1 rounded-xl border border-[var(--border-color)]">
    <button
      type="button"
      on:click={() => ($currentTab = 'chat')}
      class={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
        $currentTab === 'chat'
          ? 'bg-[var(--accent)] text-[var(--accent-text)] shadow-sm'
          : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
      }`}
    >
      💬 Text & Vision
    </button>

    <button
      type="button"
      on:click={() => ($currentTab = 'media')}
      class={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
        $currentTab === 'media'
          ? 'bg-[var(--accent)] text-[var(--accent-text)] shadow-sm'
          : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
      }`}
    >
      🎨 Image Studio
    </button>

    <button
      type="button"
      on:click={() => ($currentTab = 'voice')}
      class={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
        $currentTab === 'voice'
          ? 'bg-[var(--accent)] text-[var(--accent-text)] shadow-sm'
          : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
      }`}
    >
      🎙️ Voice Studio
    </button>

    <button
      type="button"
      on:click={() => ($currentTab = 'agent')}
      class={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
        $currentTab === 'agent'
          ? 'bg-[var(--accent)] text-[var(--accent-text)] shadow-sm'
          : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
      }`}
    >
      🤖 Agent Studio
    </button>
  </div>

  <!-- Utility Navigation -->
  <div class="flex items-center gap-2">
    <button
      type="button"
      on:click={() => ($currentTab = 'tasks')}
      class={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition border border-transparent ${
        $currentTab === 'tasks' ? 'bg-[var(--bg-base)] text-[var(--accent)] border-[var(--border-color)]' : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
      }`}
      title="Background Tasks Dashboard"
    >
      ⚡ Tasks
    </button>
    <button
      type="button"
      on:click={() => ($currentTab = 'knowledge')}
      class={`px-2 py-1.5 rounded-lg text-xs transition ${
        $currentTab === 'knowledge' ? 'bg-[var(--bg-base)] text-[var(--accent)]' : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
      }`}
      title="Knowledge Base (RAG)"
    >
      📚
    </button>
    <button
      type="button"
      on:click={() => ($currentTab = 'hf')}
      class={`px-2 py-1.5 rounded-lg text-xs transition ${
        $currentTab === 'hf' ? 'bg-[var(--bg-base)] text-[var(--accent)]' : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
      }`}
      title="HuggingFace Hub"
    >
      🌐
    </button>
    <button
      type="button"
      on:click={() => ($currentTab = 'settings')}
      class={`px-2 py-1.5 rounded-lg text-xs transition ${
        $currentTab === 'settings' ? 'bg-[var(--bg-base)] text-[var(--accent)]' : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
      }`}
      title="Settings & Theme"
    >
      ⚙️
    </button>
  </div>
</header>
