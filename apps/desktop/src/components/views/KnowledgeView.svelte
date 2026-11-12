<script lang="ts">
  import { apiFetch } from '../../lib/api';

  let kbs: any[] = [];
  let kbName = '';
  let searchQuery = '';
  let searchResults: any[] = [];

  async function loadKBs() {
    const res = await apiFetch('/knowledge-bases');
    if (res.ok) kbs = await res.json();
  }

  async function createKB() {
    if (!kbName.trim()) return;
    await apiFetch('/knowledge-bases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: kbName, description: 'Local document base' }),
    });
    kbName = '';
    loadKBs();
  }

  async function testSearch(kbId: string) {
    if (!searchQuery.trim()) return;
    const res = await apiFetch(`/knowledge-bases/${kbId}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: searchQuery, limit: 3 }),
    });
    if (res.ok) {
      const data = await res.json();
      searchResults = data.results;
    }
  }

  loadKBs();
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-5xl">
  <div>
    <h2 class="text-xl font-bold text-slate-100">Knowledge Bases (LanceDB + FastEmbed)</h2>
    <p class="text-xs text-slate-400 mt-1">CPU-bound semantic search index for your local documentation and PDFs.</p>
  </div>

  <div class="flex gap-2 max-w-md">
    <input type="text" bind:value={kbName} placeholder="New Knowledge Base Name..." class="flex-1 bg-slate-900 border border-slate-800 rounded-lg p-2 text-xs text-slate-200" />
    <button on:click={createKB} class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold rounded-lg text-white">+ Create KB</button>
  </div>

  <div class="grid grid-cols-2 gap-4">
    {#each kbs as kb}
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-3">
        <h3 class="font-bold text-sm text-indigo-400">{kb.name}</h3>
        <p class="text-xs text-slate-400">{kb.description}</p>
        <div class="flex gap-2">
          <input type="text" bind:value={searchQuery} placeholder="Semantic query..." class="flex-1 bg-slate-950 border border-slate-800 rounded p-1.5 text-xs text-slate-200" />
          <button on:click={() => testSearch(kb.id)} class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs rounded text-slate-200">Test RAG</button>
        </div>
      </div>
    {/each}
  </div>

  {#if searchResults.length > 0}
    <div class="space-y-2">
      <h4 class="text-xs font-semibold text-slate-300">Semantic Search Hits:</h4>
      {#each searchResults as r}
        <div class="p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs space-y-1">
          <p class="font-semibold text-indigo-400">{r.file_name}</p>
          <p class="text-slate-300 whitespace-pre-wrap">{r.text}</p>
        </div>
      {/each}
    </div>
  {/if}
</div>
