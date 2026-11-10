<script lang="ts">
  import hljs from 'highlight.js';
  import 'highlight.js/styles/github-dark.css';
  import { marked, type Tokens } from 'marked';
  import { apiFetch } from '../../lib/api';
  import { activeCharacterId, characters } from '../../lib/stores';

  export let messages: {
    role: string;
    content: string;
    image_paths?: string[];
    is_truncated?: boolean;
  }[] = [];
  export let onSelectQuickPrompt: (text: string) => void;
  export let onContinueMessage: () => void = () => {};

  // WhatsApp-style circular portrait avatars (no emojis)
  const personaAvatars: Record<string, string> = {
    'General Assistant': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
    'Software Architect': 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80',
    'Creative Storyteller': 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80',
    'Research Analyst': 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80',
    'Executive Brief Writer': 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80',
    'Code Reviewer': 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150&auto=format&fit=crop&q=80',
  };

  $: activePersona = $characters.find((c) => c.id === $activeCharacterId) || $characters[0];

  // In-Bubble Audio Playback State
  let activeAudio: HTMLAudioElement | null = null;
  let playingMessageIndex: number | null = null;
  let isAudioLoading: boolean = false;
  let perMessageVoice: Record<number, string> = {};

  // Modern Typed Marked.js Code Syntax Highlighting
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
      .replace(/!\[.*?\]\(.*?\)/g, '')               // Strip image tags
      .replace(/\[.*?\]\(.*?\)/g, '')               // Strip links
      .replace(/```[\s\S]*?```/g, '')               // Strip code blocks
      .replace(/`.*?`/g, '')                         // Strip inline code
      .replace(/#+\s+/g, '')                         // Strip markdown headings
      .replace(/[*_~>]/g, '')                        // Strip bold/italics/quotes
      .replace(/^(Prompt|You asked|User):.*$/gim, '') // Strip echoed user headers
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

  const starterCards = [
    {
      title: 'Vision Analysis',
      desc: 'Attach an image and ask questions about its contents',
      prompt: 'Please describe the key details of this image:',
    },
    {
      title: 'Code Architect',
      desc: 'Inspect algorithms, security, and refactoring patterns',
      prompt: 'Review this code for performance bottlenecks:',
    },
    {
      title: 'Executive Brief',
      desc: 'Summarize documents into concise spoken bullet points',
      prompt: 'Create an executive summary of the following points:',
    },
    {
      title: 'Creative Story',
      desc: 'Atmospheric storytelling with sensory depth and pacing',
      prompt: 'Write an engaging narrative about an observatory in a nebula:',
    },
  ];
</script>

<div class="flex-1 overflow-y-auto p-6 space-y-6">
  {#if messages.length === 0}
    <!-- Empty Canvas: Starter Cards -->
    <div class="h-full flex flex-col items-center justify-center text-center max-w-2xl mx-auto space-y-6 select-none">
      <div
        class="h-14 w-14 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl flex items-center justify-center text-2xl shadow-sm text-[var(--accent)] font-bold"
      >
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
        <!-- User Prompt Bubble (Color 1: Vibrant Blue / Indigo) -->
        <div class="flex justify-end">
          <div
            style="background-color: var(--bubble-user); color: var(--bubble-user-text);"
            class="max-w-2xl rounded-2xl rounded-tr-sm px-5 py-3.5 text-sm shadow-sm"
          >
            {#if msg.image_paths && msg.image_paths.length > 0}
              <div class="mb-2 p-1.5 bg-black/20 rounded text-xs font-mono">
                🖼️ Attached {msg.image_paths.length} image(s)
              </div>
            {/if}
            <p class="whitespace-pre-wrap">{msg.content}</p>
          </div>
        </div>
      {:else}
        <!-- Assistant Answer Bubble (Color 2: Slate Card / White Card) with WhatsApp-Style Avatar -->
        <div class="flex items-start gap-3 justify-start max-w-3xl">
          <!-- WhatsApp-Style Circular Avatar (No Emoji) -->
          <img
            src={personaAvatars[activePersona?.name] || personaAvatars['General Assistant']}
            alt={activePersona?.name || 'Persona'}
            class="w-9 h-9 rounded-full object-cover border border-[var(--border-color)] shadow-sm shrink-0 mt-1"
          />

          <!-- Answer Card -->
          <div
            style="background-color: var(--bubble-assistant); color: var(--bubble-assistant-text);"
            class="flex-1 rounded-2xl rounded-tl-sm px-5 py-4 text-sm border border-[var(--border-color)] shadow-sm space-y-3"
          >
            <!-- Rendered Markdown Text -->
            <div class="prose prose-sm max-w-none text-[var(--bubble-assistant-text)]">
              {@html marked.parse(msg.content)}
            </div>

            <!-- In-Bubble Voice Controls for This Specific Answer -->
            <div class="pt-3 border-t border-[var(--border-color)] flex items-center justify-between text-xs">
              <div class="flex items-center gap-2">
                <!-- Voice Selector Dropdown -->
                <select
                  bind:value={perMessageVoice[i]}
                  class="bg-[var(--bg-base)] text-[var(--text-main)] text-[11px] rounded-lg px-2 py-1 border border-[var(--border-color)] focus:outline-none cursor-pointer"
                >
                  <option value="af_heart">Voice: Heart (US Female)</option>
                  <option value="am_adam">Voice: Adam (US Male)</option>
                  <option value="bf_emma">Voice: Emma (UK Female)</option>
                </select>

                <!-- Play / Pause Button -->
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

                <!-- Stop Button -->
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

              <!-- Continue Button (if cut off by token limit) -->
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
