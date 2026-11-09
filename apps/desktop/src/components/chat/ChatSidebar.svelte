<script lang="ts">
  import { apiFetch } from '../../lib/api';
  import { activeConversationId, conversations } from '../../lib/stores';

  export let onSelectConversation: (id: string) => void;

  let editingId: string | null = null;
  let editingTitle = '';

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

  function startRename(c: any, e: Event) {
    e.stopPropagation();
    editingId = c.id;
    editingTitle = c.title;
  }

  async function saveRename(id: string, e: Event) {
    e.stopPropagation();
    if (!editingTitle.trim()) return;
    const res = await apiFetch(`/conversations/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: editingTitle.trim() }),
    });
    if (res.ok) {
      const updated = await res.json();
      $conversations = $conversations.map((c) => (c.id === id ? { ...c, title: updated.title } : c));
    }
    editingId = null;
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
    <button on:click={createNewConversation} class="w-full py-2.5 px-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition shadow">
      <span>+</span> New Conversation
    </button>

    <div class="flex-1 overflow-y-auto mt-4 space-y-1">
      {#each $conversations as c}
        <div
          role="button"
          tabindex="0"
          on:click={() => onSelectConversation(c.id)}
          on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectConversation(c.id)}
          class={`group flex items-center justify-between p-2.5 rounded-xl text-xs cursor-pointer transition select-none ${
            c.id === $activeConversationId
              ? 'bg-slate-800 text-indigo-300 font-semibold border border-slate-700'
              : 'text-slate-400 hover:bg-slate-800/50'
          }`}
        >
          {#if editingId === c.id}
            <input
              type="text"
              bind:value={editingTitle}
              on:keydown={(e) => e.key === 'Enter' && saveRename(c.id, e)}
              class="flex-1 bg-slate-900 text-xs text-slate-100 rounded px-1.5 py-0.5 border border-indigo-500 focus:outline-none"
            />
            <button
              type="button"
              on:click={(e) => saveRename(c.id, e)}
              class="text-indigo-400 hover:text-indigo-300 ml-1 px-1"
            >
              ✓
            </button>
          {:else}
            <span class="truncate flex-1 mr-2">{c.title}</span>
            <div class="opacity-0 group-hover:opacity-100 flex items-center gap-1">
              <button
                type="button"
                on:click={(e) => startRename(c, e)}
                class="text-slate-500 hover:text-slate-300 p-0.5 transition"
                title="Rename"
              >
                ✏️
              </button>
              <button
                type="button"
                on:click={(e) => deleteConversation(c.id, e)}
                class="text-slate-500 hover:text-rose-400 p-0.5 transition"
                title="Delete"
              >
                ✕
              </button>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </div>
</aside>
