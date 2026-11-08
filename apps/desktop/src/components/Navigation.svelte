<script lang="ts">
  import { currentTab } from '../lib/stores';

  const navItems: { id: any; icon: string; label: string }[] = [
    { id: 'chat', icon: '💬', label: 'Multimodal Chat' },
    { id: 'characters', icon: '🤖', label: 'Character Studio' },
    { id: 'knowledge', icon: '📚', label: 'Knowledge Base (RAG)' },
    { id: 'media', icon: '🎨', label: 'Media Studio (ComfyUI & Audio)' },
    { id: 'tasks', icon: '⚡', label: 'Task Queue Dashboard' },
    { id: 'hf', icon: '🌐', label: 'HuggingFace Hub' },
    { id: 'settings', icon: '⚙️', label: 'System & Hardware' },
  ];
</script>

<nav class="w-16 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-4 justify-between select-none">
  <div class="flex flex-col items-center space-y-6 w-full">
    <!-- Brand Avatar -->
    <div class="h-10 w-10 bg-indigo-600 rounded-xl flex items-center justify-center font-black text-lg text-white shadow-lg shadow-indigo-600/30">
      A
    </div>

    <!-- Nav Items -->
    <div class="flex flex-col space-y-2 w-full px-2">
      {#each navItems as item}
        <button
          on:click={() => ($currentTab = item.id)}
          class={`relative p-3 rounded-xl flex items-center justify-center text-lg transition group ${
            $currentTab === item.id
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40 shadow-inner'
              : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
          title={item.label}
        >
          {item.icon}
          {#if $currentTab === item.id}
            <span class="absolute left-0 top-2.5 bottom-2.5 w-1 bg-indigo-500 rounded-r"></span>
          {/if}
        </button>
      {/each}
    </div>
  </div>

  <div class="text-[10px] font-mono text-slate-600">v0.1</div>
</nav>
