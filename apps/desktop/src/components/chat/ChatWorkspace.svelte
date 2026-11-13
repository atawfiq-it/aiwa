<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import {
    activeCharacterId,
    activeConversationId,
    characters,
    conversations,
    supervisorStatus,
  } from '../../lib/stores';
  import ChatHeader from './ChatHeader.svelte';
  import ChatSidebar from './ChatSidebar.svelte';
  import InputBar from './InputBar.svelte';
  import MessageList from './MessageList.svelte';
  import PersonaPanel from './PersonaPanel.svelte';

  let messages: {
    role: string;
    content: string;
    image_paths?: string[];
    is_truncated?: boolean;
  }[] = [];
  let isStreaming = false;
  let isPersonaPanelOpen = true;
  let currentAbortController: AbortController | null = null;

  async function loadConversation(id: string) {
    $activeConversationId = id;
    const res = await apiFetch(`/conversations/${id}`);
    if (res.ok) {
      const data = await res.json();
      messages = data.messages.map((m: any) => ({
        role: m.role,
        content: m.content,
      }));

      // If conversation has an associated character, sync active persona
      if (data.conversation?.character_id) {
        $activeCharacterId = data.conversation.character_id;
        localStorage.setItem('aiwa_active_character_id', data.conversation.character_id);
      }
    }
  }

  function stopGeneration() {
    if (currentAbortController) {
      currentAbortController.abort();
      currentAbortController = null;
      isStreaming = false;
    }
  }

  function populateQuickPrompt(promptTextTemplate: string) {
    const inputElement = document.querySelector('input[type="text"]') as HTMLInputElement;
    if (inputElement) {
      inputElement.value = promptTextTemplate + ' ';
      inputElement.focus();
      inputElement.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  function continueLastMessage() {
    if (messages.length === 0 || isStreaming) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.role === 'assistant') {
      lastMsg.is_truncated = false;
      handleSend('Please continue writing from exactly where you left off, without repeating yourself.', []);
    }
  }

  async function handleSend(text: string, images: string[]) {
    // 1. Ensure conversation exists in SQLite
    if (!$activeConversationId) {
      const convRes = await apiFetch('/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: text.slice(0, 32),
          character_id: $activeCharacterId || null,
        }),
      });
      if (convRes.ok) {
        const c = await convRes.json();
        $conversations = [c, ...$conversations];
        $activeConversationId = c.id;
      }
    }

    // 2. Persist User Prompt to SQLite immediately
    await apiFetch(`/conversations/${$activeConversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: 'user', content: text }),
    });

    // Refresh conversation list to capture auto-generated title
    apiFetch('/conversations').then(async (res) => {
      if (res.ok) $conversations = await res.json();
    });

    messages = [...messages, { role: 'user', content: text, image_paths: images }];
    isStreaming = true;
    currentAbortController = new AbortController();

    const assistantIdx = messages.length;
    messages = [...messages, { role: 'assistant', content: '' }];

    // Resolve Persona ID and Name robustly
    const charIdToSend = $activeCharacterId || localStorage.getItem('aiwa_active_character_id') || '';
    const activeCharObj = $characters.find((c) => c.id === charIdToSend);
    const charNameToSend = activeCharObj?.name || localStorage.getItem('aiwa_active_character_name') || '';

    console.log('[AIWA DISPATCH CHAT]', {
      conversation_id: $activeConversationId,
      character_id: charIdToSend,
      character_name: charNameToSend,
    });

    try {
      const response = await apiFetch('/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: currentAbortController.signal,
        body: JSON.stringify({
          conversation_id: $activeConversationId,
          character_id: charIdToSend || null,
          character_name: charNameToSend || null,
          messages: messages.slice(0, -1),
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        messages[assistantIdx].content = `⚠️ Error (${response.status}): ${err.detail || 'Inference engine failed'}`;
        messages = [...messages];
        return;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6).trim());
              if (data.text) {
                messages[assistantIdx].content += data.text;
                messages = [...messages];
              }
              if (data.finish_reason === 'length') {
                messages[assistantIdx].is_truncated = true;
                messages = [...messages];
              }
              if (data.error) {
                messages[assistantIdx].content = `⚠️ ${data.error}`;
                messages = [...messages];
              }
            } catch {}
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        messages[assistantIdx].content += ' [Generation stopped by user]';
      } else {
        messages[assistantIdx].content += `\n[Network Error: ${e.message}]`;
      }
      messages = [...messages];
    } finally {
      isStreaming = false;
      currentAbortController = null;
    }
  }

  onMount(() => {
    if ($conversations.length > 0 && !$activeConversationId) {
      loadConversation($conversations[0].id);
    }
  });
</script>

<div class="flex-1 flex overflow-hidden relative">
  <!-- Conversation History Sidebar -->
  <ChatSidebar onSelectConversation={loadConversation} />

  <!-- Center Chat Space -->
  <div class="flex-1 flex flex-col bg-[var(--bg-base)] overflow-hidden">
    <!-- Header with Model & Persona Selectors -->
    <ChatHeader bind:isPersonaPanelOpen />

    <!-- No Model Warning Banner -->
    {#if $supervisorStatus?.state !== 'Ready'}
      <div class="px-6 py-2.5 bg-amber-500/10 border-t border-b border-amber-500/30 flex items-center justify-between text-xs text-amber-300 select-none shrink-0">
        <div class="flex items-center gap-2">
          <span>⚠️</span>
          <span><strong>No Model Loaded:</strong> Please select a model in the header and click <strong>Apply</strong> before chatting.</span>
        </div>
      </div>
    {/if}

    <!-- Message Bubble List -->
    <MessageList
      {messages}
      onSelectQuickPrompt={populateQuickPrompt}
      onContinueMessage={continueLastMessage}
    />

    <!-- Input Bar with Morphing Stop Button -->
    <InputBar
      {isStreaming}
      onSendMessage={handleSend}
      onStopGeneration={stopGeneration}
    />
  </div>

  <!-- Collapsed Tab to Restore Persona Panel on Right Edge -->
  {#if !isPersonaPanelOpen}
    <button
      type="button"
      on:click={() => (isPersonaPanelOpen = true)}
      class="absolute right-0 top-1/2 -translate-y-1/2 bg-[var(--bg-card)] border-l border-y border-[var(--border-color)] px-1.5 py-4 rounded-l-xl text-xs text-[var(--text-muted)] hover:text-indigo-400 hover:bg-[var(--bg-base)] shadow-lg transition flex flex-col items-center gap-1 z-10 select-none"
      title="Open Persona Profile"
    >
      <span>👤</span>
      <span class="text-[9px] font-mono [writing-mode:vertical-lr]">PERSONA</span>
    </button>
  {/if}

  <!-- Persona Drawer -->
  <PersonaPanel {isStreaming} bind:isOpen={isPersonaPanelOpen} />
</div>
