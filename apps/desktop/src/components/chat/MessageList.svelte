<script lang="ts">
  import hljs from 'highlight.js';
  import 'highlight.js/styles/github-dark.css';
  import { marked, type Tokens } from 'marked';
  import { apiFetch } from '../../lib/api';

  export let messages: {
    role: string;
    content: string;
    image_paths?: string[];
    is_truncated?: boolean;
  }[] = [];
  export let onSelectQuickPrompt: (text: string) => void;
  export let onContinueMessage: () => void = () => {};

  let activeAudio: HTMLAudioElement | null = null;
  let playingIndex: number | null = null;

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
      .replace(/!\[.*?\]\(.*?\)/g, '')       // Remove image tags ![alt](url)
      .replace(/\[.*?\]\(.*?\)/g, '')       // Remove links [text](url)
      .replace(/```[\s\S]*?```/g, '')       // Remove code blocks
      .replace(/`.*?`/g, '')                 // Remove inline code
      .replace(/#+\s+/g, '')                 // Remove headings
      .replace(/[*_~>]/g, '')                // Remove markdown formatting
      .replace(/^(Prompt|You asked|User):.*$/gim, '') // Remove echoed prompt headers
      .trim();
  }

  async function speakMessage(content: string, index: number) {
    if (playingIndex === index && activeAudio) {
      activeAudio.pause();
      playingIndex = null;
      return;
    }

    const cleanText = cleanTextForSpeech(content);
    if (!cleanText) {
      alert('No speakable text found in message.');
      return;
    }

    try {
      const res = await apiFetch('/media/audio/speech-direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleanText.slice(0, 500) }),
      });
      if (res.ok) {
        const blob = await res.blob();
        if (activeAudio) activeAudio.pause();
        activeAudio = new Audio(URL.createObjectURL(blob));
        playingIndex = index;
        activeAudio.play();
        activeAudio.onended = () => {
          playingIndex = null;
        };
      }
    } catch (e) {
      alert('Failed generating audio reply.');
    }
  }

  const starterCards = [
    { title: 'Vision Analysis', desc: 'Attach an image and ask questions about it', prompt: 'Please describe the key details of this image.' },
    { title: 'Code Architect', desc: 'Inspect algorithms, security, and refactoring', prompt: 'Review this Python code for performance bottlenecks:' },
    { title: 'Executive Brief', desc: 'Summarize documents into concise bullet points', prompt: 'Create an executive summary of the following points:' },
    { title: 'Creative Story', desc: 'Atmospheric storytelling with sensory depth', prompt: 'Write a cinematic story about an observatory in a nebula.' },
  ];
</script>

<div class="flex-1 overflow-y-auto p-6 space-y-6">
  {#if messages.length === 0}
    <!-- Rich Starter Canvas -->
    <div class="h-full flex flex-col items-center justify-center text-center max-w-2xl mx-auto space-y-6 select-none">
      <div class="h-14 w-14 bg-indigo-600/20 border border-indigo-500/30 rounded-2xl flex items-center justify-center text-2xl text-indigo-400 shadow-xl">
        ⚡
      </div>
      <div>
        <h2 class="text-xl font-bold text-slate-100">Welcome to AIWA Workstation</h2>
        <p class="text-xs text-slate-400 mt-1 max-w-md">Your local-first multimodal platform for Vision-Language, Audio, Diffusion, and RAG.</p>
      </div>

      <div class="grid grid-cols-2 gap-3 w-full text-left">
        {#each starterCards as card}
          <button
            on:click={() => onSelectQuickPrompt(card.prompt)}
            class="p-4 bg-slate-900 border border-slate-800 hover:border-indigo-500/50 hover:bg-slate-800/60 rounded-xl transition group text-left"
          >
            <h3 class="text-xs font-bold text-indigo-400 group-hover:text-indigo-300">{card.title}</h3>
            <p class="text-[11px] text-slate-400 mt-1">{card.desc}</p>
          </button>
        {/each}
      </div>
    </div>
  {:else}
    <!-- Message Bubbles -->
    {#each messages as msg, i}
      <div class={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
        <div class={`max-w-3xl rounded-2xl px-5 py-4 text-sm shadow-md ${
          msg.role === 'user'
            ? 'bg-indigo-600 text-white rounded-br-none'
            : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none'
        }`}>
          <!-- User Image Attachment Preview -->
          {#if msg.image_paths && msg.image_paths.length > 0}
            <div class="mb-3 flex items-center gap-2 p-2 bg-black/20 rounded-lg text-xs font-mono">
              <span>🖼️ Attached: {msg.image_paths.length} file(s)</span>
            </div>
          {/if}

          <!-- Message Text -->
          {#if msg.role === 'user'}
            <p class="whitespace-pre-wrap">{msg.content}</p>
          {:else}
            <div class="prose prose-invert prose-sm max-w-none prose-pre:bg-slate-950 prose-pre:border prose-pre:border-slate-800">
              {@html marked.parse(msg.content)}
            </div>

            <!-- Assistant Actions: Text-to-Speech Button -->
            <div class="mt-3 pt-2 border-t border-slate-800/80 flex items-center gap-2">
              <button
                type="button"
                on:click={() => speakMessage(msg.content, i)}
                class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-[11px] font-medium text-slate-300 rounded-md flex items-center gap-1.5 transition"
              >
                {playingIndex === i ? '⏸️ Pause Speech' : '🔊 Listen (Kokoro)'}
              </button>

              <!-- Show Continue Button if message was cut off by token limit -->
              {#if msg.is_truncated}
                <button
                  type="button"
                  on:click={onContinueMessage}
                  class="px-2.5 py-1 bg-indigo-600/30 hover:bg-indigo-600 border border-indigo-500/40 text-[11px] font-bold text-indigo-300 hover:text-white rounded-md flex items-center gap-1 transition"
                >
                  ▶️ Continue Generating
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {/each}
  {/if}
</div>
