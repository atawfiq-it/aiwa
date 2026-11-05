<script lang="ts">
  import { currentTab } from '../lib/stores';
</script>

<nav class="w-16 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-4 space-y-6">
  <div class="h-10 w-10 bg-indigo-600 rounded-xl flex items-center justify-center font-bold text-lg text-white shadow-lg">A</div>
  <div class="flex flex-col space-y-4 w-full px-2">
    <button on:click={() => ($currentTab = 'chat')} class={`p-3 rounded-lg flex justify-center transition ${$currentTab === 'chat' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`} title="AI Chat">💬</button>
    <button on:click={() => ($currentTab = 'hf')} class={`p-3 rounded-lg flex justify-center transition ${$currentTab === 'hf' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`} title="HuggingFace Hub">🌐</button>
    <button on:click={() => ($currentTab = 'settings')} class={`p-3 rounded-lg flex justify-center transition ${$currentTab === 'settings' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`} title="Model Scanner & Settings">⚙️</button>
  </div>
</nav>
