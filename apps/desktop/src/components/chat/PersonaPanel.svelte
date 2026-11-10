<script lang="ts">
  import { activeCharacterId, characters } from '../../lib/stores';

  export let isStreaming: boolean = false;
  export let isOpen: boolean = true;

  $: activePersona = $characters.find((c) => c.id === $activeCharacterId) || $characters[0];

  // Visual portrait avatars mapped to starter personas
  const avatarPortraits: Record<string, string> = {
    'General Assistant': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500&auto=format&fit=crop&q=80',
    'Software Architect': 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=500&auto=format&fit=crop&q=80',
    'Creative Storyteller': 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=500&auto=format&fit=crop&q=80',
    'Research Analyst': 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=500&auto=format&fit=crop&q=80',
    'Executive Brief Writer': 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=500&auto=format&fit=crop&q=80',
    'Code Reviewer': 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=500&auto=format&fit=crop&q=80',
  };
</script>

{#if isOpen}
  <aside class="w-80 bg-[var(--bg-card)] border-l border-[var(--border-color)] p-6 flex flex-col justify-between overflow-y-auto select-none">
    <div class="space-y-6 text-center">
      <!-- Persona Header -->
      <div class="flex items-center justify-between pb-3 border-b border-[var(--border-color)]">
        <span class="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">Active Persona</span>
        <button on:click={() => (isOpen = false)} class="text-xs text-[var(--text-muted)] hover:text-[var(--text-main)]" title="Hide Panel">✕</button>
      </div>

      <!-- Persona Portrait Card -->
      <div class="relative mx-auto w-44 h-56 rounded-2xl overflow-hidden border-2 border-[var(--border-color)] shadow-2xl group">
        <img
          src={avatarPortraits[activePersona?.name] || avatarPortraits['General Assistant']}
          alt={activePersona?.name}
          class="w-full h-full object-cover group-hover:scale-105 transition duration-500"
        />

        <!-- Status Glow Overlay -->
        <div class="absolute bottom-0 inset-x-0 p-2.5 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center justify-center gap-1.5">
          <span class={`h-2.5 w-2.5 rounded-full ${isStreaming ? 'bg-amber-400 animate-ping' : 'bg-[var(--accent)]'}`}></span>
          <span class="text-[11px] font-bold text-white uppercase tracking-wider">
            {isStreaming ? 'Thinking...' : 'Active Presence'}
          </span>
        </div>
      </div>

      <!-- Identity (Clean, No Emoji) -->
      <div>
        <h3 class="font-bold text-base text-[var(--text-main)] tracking-tight">{activePersona?.name}</h3>
        <p class="text-xs text-[var(--text-muted)] mt-1">{activePersona?.description || 'Active Character Persona'}</p>
      </div>

      <!-- Details Card -->
      <div class="bg-[var(--bg-base)] p-3.5 rounded-xl border border-[var(--border-color)] text-left text-xs space-y-2">
        <div class="flex justify-between">
          <span class="text-[var(--text-muted)]">Voice:</span>
          <span class="font-mono text-[var(--accent)] font-semibold">{activePersona?.voice_persona || 'af_heart'}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-[var(--text-muted)]">Temperature:</span>
          <span class="font-mono text-slate-300 font-semibold">{activePersona?.temperature || 0.7}</span>
        </div>
      </div>
    </div>
  </aside>
{/if}
