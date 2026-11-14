<script lang="ts">
  import hljs from 'highlight.js';
  import 'highlight.js/styles/github-dark.css';
  import { marked, type Tokens } from 'marked';
  import { apiFetch } from '../../lib/api';
  import {
    activeCharacterId,
    activeConversationId,
    characters,
    sessionToken,
  } from '../../lib/stores';

  export let messages: {
    id?: string;
    role: string;
    content: string;
    image_paths?: string[];
    is_truncated?: boolean;
  }[] = [];
  export let onSelectQuickPrompt: (text: string) => void;
  export let onContinueMessage: () => void = () => {};
  export let onReloadMessages: () => void = () => {};

  $: activePersona = $characters.find((c) => c.id === $activeCharacterId) || $characters[0];

  // In-Bubble Audio Playback State
  let activeAudio: HTMLAudioElement | null = null;
  let playingMessageIndex: number | null = null;
  let isAudioLoading: boolean = false;
  let perMessageVoice: Record<number, string> = {};

  // Inline Message Editing State
  let editingMessageId: string | null = null;
  let editingContent = '';

  marked.use({
    renderer: {
      code(token: Tokens.Code): string {
        const lang = token.lang && hljs.getLanguage(token.lang) ? token.lang : 'plaintext';
        const highlighted = hljs.highlight(token.text, { language: lang }).value;
        return `<pre><code class="hljs ${lang}">${highlighted}</code></pre>`;
      },
    },
  });

  function cleanTextForSpeech(raw: string): string {
    return raw
      .replace(/!\[.*?\]\(.*?\)/g, '')
      .replace(/\[.*?\]\(.*?\)/g, '')
      .replace(/```[\s\S]*?```/g, '')
      .replace(/`.*?`/g, '')
      .replace(/#+\s+/g, '')
      .replace(/[*_~>]/g, '')
      .replace(/^(Prompt|You asked|User):.*$/gim, '')
      .trim();
  }

  async function togglePlaySpeech(content: string, index: number) {
    if (playingMessageIndex === index && activeAudio) {
      if (!activeAudio.paused) {
        activeAudio.pause();
      } else {
        activeAudio.play();
      }
      return;
    }

    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }

    const cleanText = cleanTextForSpeech(content);
    if (!cleanText) return;

    isAudioLoading = true;
    playingMessageIndex = index;
    const voiceToUse = perMessageVoice[index] || activePersona?.voice_persona || 'af_heart';

    try {
      const res = await apiFetch('/media/audio/speech-direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleanText, voice: voiceToUse }),
      });

      if (res.ok) {
        const blob = await res.blob();
        activeAudio = new Audio(URL.createObjectURL(blob));
        activeAudio.play();
        activeAudio.onended = () => {
          playingMessageIndex = null;
        };
      } else {
        playingMessageIndex = null;
      }
    } catch {
      playingMessageIndex = null;
    } finally {
      isAudioLoading = false;
    }
  }

  function stopSpeech() {
    if (activeAudio) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
      activeAudio = null;
    }
    playingMessageIndex = null;
  }

  function startEdit(msg: any) {
    editingMessageId = msg.id;
    editingContent = msg.content;
  }

  async function saveEdit(msgId: string) {
    if (!$activeConversationId || !editingContent.trim()) return;
    const res = await apiFetch(`/conversations/${$activeConversationId}/messages/${msgId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: editingContent }),
    });
    if (res.ok) {
      editingMessageId = null;
      onReloadMessages();
    }
  }

  async function deleteMessage(msgId: string) {
    if (!$activeConversationId || !confirm('Permanently delete this message?')) return;
    const res = await apiFetch(`/conversations/${$activeConversationId}/messages/${msgId}`, {
      method: 'DELETE',
    });
    if (res.ok) {
      onReloadMessages();
    }
  }

  const starterCards = [
    { title: 'Vision Analysis', desc: 'Attach an image and ask questions about it', prompt: 'Please describe the key details of this image.' },
    { title: 'Code Architect', desc: 'Inspect algorithms, security, and refactoring', prompt: 'Review this code for performance bottlenecks:' },
    { title: 'Executive Brief', desc: 'Summarize documents into concise bullet points', prompt: 'Create an executive summary of the following points:' },
    { title: 'Creative Story', desc: 'Atmospheric storytelling with sensory depth', prompt: 'Write an engaging story about an observatory in a nebula.' },
  ];
</script>

<div class="flex-1 overflow-y-auto p-6 space-y-6">
  {#if messages.length === 0}
    <!-- Starter Cards -->
    <div class="h-full flex flex-col items-center justify-center text-center max-w-2xl mx-auto space-y-6 select-none">
      <div class="h-14 w-14 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl flex items-center justify-center text-2xl shadow-sm text-[var(--accent)] font-bold">
        A
      </div>
      <div>
        <h2 class="text-xl font-bold text-[var(--text-main)]">AIWA Workstation</h2>
        <p class="text-xs text-[var(--text-muted)] mt-1">Select a prompt below or start typing to chat with your local models.</p>
      </div>

      <div class="grid grid-cols-2 gap-3 w-full text-left">
        {#each starterCards as card}
          <button
            type="button"
            on:click={() => onSelectQuickPrompt(card.prompt)}
            class="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--accent)] rounded-2xl transition group text-left shadow-sm"
          >
            <h3 class="text-xs font-bold text-[var(--text-main)] group-hover:text-[var(--accent)]">{card.title}</h3>
            <p class="text-[11px] text-[var(--text-muted)] mt-1">{card.desc}</p>
          </button>
        {/each}
      </div>
    </div>
  {:else}
    <!-- Chat Bubbles -->
    {#each messages as msg, i}
      {#if msg.role === 'user'}
        <!-- User Prompt Bubble -->
        <div class="flex justify-end group items-start gap-2">
          <!-- Edit & Delete Hover Actions -->
          <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition select-none mt-2">
            <button
              type="button"
              on:click={() => startEdit(msg)}
              class="text-slate-400 hover:text-indigo-400 p-1 text-xs"
              title="Edit Prompt"
            >
              ✏️
            </button>
            <button
              type="button"
              on:click={() => msg.id && deleteMessage(msg.id)}
              class="text-slate-400 hover:text-rose-400 p-1 text-xs"
              title="Delete Prompt"
            >
              ✕
            </button>
          </div>

          <div
            style="background-color: var(--bubble-user); color: var(--bubble-user-text);"
            class="max-w-2xl rounded-2xl rounded-tr-sm px-5 py-3.5 text-sm shadow-sm"
          >
            {#if msg.image_paths && msg.image_paths.length > 0}
              <div class="mb-2 p-1.5 bg-black/20 rounded text-xs font-mono">
                🖼️ Attached {msg.image_paths.length} image(s)
              </div>
            {/if}

            {#if editingMessageId === msg.id}
              <textarea
                rows="3"
                bind:value={editingContent}
                class="w-full bg-black/20 text-white rounded-lg p-2 text-xs focus:outline-none font-sans"
              ></textarea>
              <div class="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  on:click={() => (editingMessageId = null)}
                  class="px-2 py-0.5 text-xs text-white/70 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  on:click={() => msg.id && saveEdit(msg.id)}
                  class="px-3 py-0.5 bg-white text-indigo-700 font-bold rounded-md text-xs"
                >
                  Save
                </button>
              </div>
            {:else}
              <p class="whitespace-pre-wrap">{msg.content}</p>
            {/if}
          </div>
        </div>
      {:else}
        <!-- Assistant Answer Bubble with Local Disk Avatar -->
        <div class="flex items-start gap-3 justify-start max-w-3xl group">
          <img
            src={`http://127.0.0.1:8000/api/v1/characters/avatars/${activePersona?.name || 'default'}?token=${$sessionToken}`}
            alt={activePersona?.name}
            class="w-9 h-9 rounded-full object-cover border border-[var(--border-color)] shadow-sm shrink-0 mt-1 bg-[var(--bg-card)]"
          />

          <div
            style="background-color: var(--bubble-assistant); color: var(--bubble-assistant-text);"
            class="flex-1 rounded-2xl rounded-tl-sm px-5 py-4 text-sm border border-[var(--border-color)] shadow-sm space-y-3 relative"
          >
            <!-- Edit & Delete Hover Actions -->
            <div class="absolute top-2 right-3 opacity-0 group-hover:opacity-100 flex items-center gap-1 transition select-none">
              <button
                type="button"
                on:click={() => startEdit(msg)}
                class="text-[var(--text-muted)] hover:text-indigo-400 p-1 text-xs"
                title="Edit Response"
              >
                ✏️
              </button>
              <button
                type="button"
                on:click={() => msg.id && deleteMessage(msg.id)}
                class="text-[var(--text-muted)] hover:text-rose-400 p-1 text-xs"
                title="Delete Response"
              >
                ✕
              </button>
            </div>

            {#if editingMessageId === msg.id}
              <textarea
                rows="5"
                bind:value={editingContent}
                class="w-full bg-[var(--bg-base)] text-[var(--text-main)] rounded-lg p-2.5 text-xs border border-[var(--border-color)] focus:outline-none"
              ></textarea>
              <div class="flex justify-end gap-2">
                <button
                  type="button"
                  on:click={() => (editingMessageId = null)}
                  class="px-2.5 py-1 text-xs text-[var(--text-muted)]"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  on:click={() => msg.id && saveEdit(msg.id)}
                  class="px-3 py-1 bg-indigo-600 text-white font-bold rounded-lg text-xs"
                >
                  Save
                </button>
              </div>
            {:else}
              <div class="prose prose-sm max-w-none text-[var(--bubble-assistant-text)]">
                {@html marked.parse(msg.content)}
              </div>
            {/if}

            <!-- In-Bubble Speech & Action Controls -->
            <div class="pt-3 border-t border-[var(--border-color)] flex items-center justify-between text-xs">
              <div class="flex items-center gap-2">
                <select
                  bind:value={perMessageVoice[i]}
                  class="bg-[var(--bg-base)] text-[var(--text-main)] text-[11px] rounded-lg px-2 py-1 border border-[var(--border-color)] focus:outline-none cursor-pointer"
                >
                  <option value="af_heart">Voice: Heart (US Female)</option>
                  <option value="am_adam">Voice: Adam (US Male)</option>
                  <option value="bf_emma">Voice: Emma (UK Female)</option>
                </select>

                <button
                  type="button"
                  on:click={() => togglePlaySpeech(msg.content, i)}
                  class="px-2.5 py-1 bg-[var(--bg-base)] hover:opacity-80 border border-[var(--border-color)] rounded-lg text-[11px] font-semibold flex items-center gap-1 transition"
                >
                  {#if isAudioLoading && playingMessageIndex === i}
                    <span>🌀 Loading...</span>
                  {:else if playingMessageIndex === i && activeAudio && !activeAudio.paused}
                    <span>⏸️ Pause</span>
                  {:else}
                    <span>▶️ Play</span>
                  {/if}
                </button>

                {#if playingMessageIndex === i}
                  <button
                    type="button"
                    on:click={stopSpeech}
                    class="px-2 py-1 bg-rose-500/10 text-rose-500 border border-rose-500/30 rounded-lg text-[11px] font-semibold"
                  >
                    ⏹️ Stop
                  </button>
                {/if}
              </div>

              {#if msg.is_truncated}
                <button
                  type="button"
                  on:click={onContinueMessage}
                  class="px-2.5 py-1 bg-indigo-600/20 text-indigo-500 border border-indigo-500/30 rounded-lg text-[11px] font-bold hover:bg-indigo-600 hover:text-white transition"
                >
                  ▶️ Continue
                </button>
              {/if}
            </div>
          </div>
        </div>
      {/if}
    {/each}
  {/if}
</div>
