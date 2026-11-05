<script lang="ts">
  import { apiFetch } from '../../lib/api';
  import { activeConversationId, conversations } from '../../lib/stores';

  export let onSelectConversation: (id: string) => void;

  async function createNewConversation() {
    const res = await apiFetch('/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New Conversation' }),
    });
    if (res.ok) {
      const newConv = await res.json();
      $conversations = [newConv, ...$conversations];
      onSelectConversation(newConv.id);
    }
  }

  async function deleteConversation(id: string, e: Event) {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;
    const res = await apiFetch(`/conversations/${id}`, { method: 'DELETE' });
    if (res.ok) {
      $conversations = $conversations.filter((c) => c.id !== id);
      if ($activeConversationId === id) {
        if ($conversations.length > 0) onSelectConversation($conversations[0].id);
        else $activeConversationId = null;
      }
    }
  }
</script>

<aside class="w-64 bg-slate-900/60 border-r border-slate-800 flex flex-col justify-between">
  <div class="p-4 flex flex-col h-full">
    <button on:click={createNewConversation} class="w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition shadow">
      <span>+</span> New Conversation
    </button>

    <div class="flex-1 overflow-y-auto mt-4 space-y-1">
      {#each $conversations as c}
        <div
          on:click={() => onSelectConversation(c.id)}
          class={`group flex items-center justify-between p-2.5 rounded-lg text-xs cursor-pointer transition ${c.id === $activeConversationId ? 'bg-slate-800 text-indigo-300 font-semibold border border-slate-700' : 'text-slate-400 hover:bg-slate-800/50'}`}
        >
          <span class="truncate flex-1 mr-2">{c.title}</span>
          <button on:click={(e) => deleteConversation(c.id, e)} class="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 p-1 transition">✕</button>
        </div>
      {/each}
    </div>
  </div>
</aside>
