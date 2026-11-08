<script lang="ts">
  import { apiFetch } from '../../lib/api';
  import { activeCharacterId, characters } from '../../lib/stores';

  let newName = '';
  let newEmoji = '🤖';
  let newVoice = 'af_heart';
  let newPrompt = '';

  async function createCharacter() {
    if (!newName.trim() || !newPrompt.trim()) return;
    const res = await apiFetch('/characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: newName,
        avatar_emoji: newEmoji,
        voice_persona: newVoice,
        system_prompt: newPrompt,
        temperature: 0.7,
      }),
    });
    if (res.ok) {
      const created = await res.json();
      $characters = [...$characters, created];
      newName = '';
      newPrompt = '';
    }
  }
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-5xl">
  <div>
    <h2 class="text-xl font-bold text-slate-100">Character & Persona Studio</h2>
    <p class="text-xs text-slate-400 mt-1">Configure system prompts, personalities, and bound Kokoro voice profiles.</p>
  </div>

  <div class="grid grid-cols-3 gap-4">
    {#each $characters as c}
      <div class={`p-5 rounded-xl border transition flex flex-col justify-between ${
        $activeCharacterId === c.id ? 'bg-indigo-950/20 border-indigo-500' : 'bg-slate-900 border-slate-800'
      }`}>
        <div>
          <div class="text-3xl mb-2">{c.avatar_emoji}</div>
          <h3 class="font-bold text-sm text-slate-200">{c.name}</h3>
          <p class="text-[11px] text-slate-400 mt-1">{c.description || 'Custom Persona'}</p>
          <div class="mt-3 p-2.5 bg-slate-950 rounded-lg text-[11px] text-slate-400 font-mono line-clamp-3">
            {c.system_prompt}
          </div>
        </div>

        <button
          on:click={() => ($activeCharacterId = c.id)}
          class={`mt-4 w-full py-1.5 rounded-lg text-xs font-semibold transition ${
            $activeCharacterId === c.id ? 'bg-indigo-600 text-white' : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
          }`}
        >
          {$activeCharacterId === c.id ? 'Active Persona' : 'Select Persona'}
        </button>
      </div>
    {/each}
  </div>

  <!-- Create Persona Form -->
  <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4 max-w-2xl">
    <h3 class="text-sm font-bold text-slate-200">+ Create Custom Character</h3>
    <div class="grid grid-cols-3 gap-3">
      <input type="text" bind:value={newName} placeholder="Character Name..." class="col-span-2 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200" />
      <input type="text" bind:value={newEmoji} placeholder="Emoji (e.g. 🧙)" class="bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-center" />
    </div>
    <textarea rows="3" bind:value={newPrompt} placeholder="System instructions / Persona behavior..." class="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-slate-200"></textarea>
    <button on:click={createCharacter} class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold rounded-lg text-white">Save Character</button>
  </div>
</div>
