<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import {
    activeCharacterId,
    activeConversationId,
    characters,
    conversations,
    registeredModels,
    supervisorStatus,
  } from '../../lib/stores';
  import ChatHeader from './ChatHeader.svelte';
  import ChatSidebar from './ChatSidebar.svelte';
  import InputBar from './InputBar.svelte';
  import MessageList from './MessageList.svelte';
  import PersonaPanel from './PersonaPanel.svelte';

  let messages: {
    id?: string;
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
        id: m.id,
        role: m.role,
        content: m.content,
      }));
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
      handleSend(
        'Please continue writing from exactly where you left off, without repeating yourself.',
        []
      );
    }
  }

  async function handleSend(text: string, images: string[]) {
    if (!$activeConversationId) {
      const convRes = await apiFetch('/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: text.slice(0, 30) }),
      });
      if (convRes.ok) {
        const c = await convRes.json();
        $conversations = [c, ...$conversations];
        $activeConversationId = c.id;
      }
    }

    // Persist user prompt to SQLite
    await apiFetch(`/conversations/${$activeConversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: 'user', content: text }),
    });

    apiFetch('/conversations').then(async (res) => {
      if (res.ok) $conversations = await res.json();
    });

    messages = [...messages, { role: 'user', content: text, image_paths: images }];
    isStreaming = true;
    currentAbortController = new AbortController();

    const assistantIdx = messages.length;
    messages = [...messages, { role: 'assistant', content: '' }];

    const charIdToSend = $activeCharacterId || localStorage.getItem('aiwa_active_character_id') || '';
    const charNameToSend = localStorage.getItem('aiwa_active_character_name') || '';

    let hasReceivedText = false;

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
        messages[assistantIdx].content = `⚠️ Error: ${err.detail || `HTTP ${response.status}`}`;
        messages = [...messages];
        return;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        for (const line of decoder.decode(value).split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6).trim());

              if (data.status && !hasReceivedText) {
                messages[assistantIdx].content = `*⏳ ${data.status}*`;
                messages = [...messages];
              }

              if (data.error) {
                messages[assistantIdx].content = `⚠️ ${data.error}`;
                messages = [...messages];
                hasReceivedText = true;
              }

              if (data.text) {
                if (!hasReceivedText) {
                  messages[assistantIdx].content = '';
                  hasReceivedText = true;
                }
                messages[assistantIdx].content += data.text;
                messages = [...messages];
              }

              if (data.finish_reason === 'length') {
                messages[assistantIdx].is_truncated = true;
                messages = [...messages];
              }
            } catch {}
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        messages[assistantIdx].content += ' [Generation stopped]';
      } else {
        messages[assistantIdx].content += `\n[Error: ${e.message}]`;
      }
      messages = [...messages];
    } finally {
      isStreaming = false;
      currentAbortController = null;
      // Refresh supervisor status after lazy load or generation
      apiFetch('/models/status').then(async (r) => {
        if (r.ok) supervisorStatus.set(await r.json());
      });
    }
  }

  onMount(async () => {
    if ($registeredModels.length === 0) {
      const res = await apiFetch('/models');
      if (res.ok) $registeredModels = await res.json();
    }
    if ($characters.length === 0) {
      const res = await apiFetch('/characters');
      if (res.ok) $characters = await res.json();
    }
    if ($conversations.length > 0 && !$activeConversationId) {
      loadConversation($conversations[0].id);
    }
  });
</script>

<div class="flex-1 flex overflow-hidden">
  <!-- Left Conversation Sidebar -->
  <ChatSidebar onSelectConversation={loadConversation} />

  <!-- Main Center Column -->
  <div class="flex-1 flex flex-col bg-[var(--bg-base)] overflow-hidden">
    <ChatHeader bind:isPersonaPanelOpen />

    {#if $registeredModels.length === 0}
      <div class="px-6 py-2 bg-amber-500/10 border-b border-amber-500/30 flex items-center gap-2 text-xs text-amber-400 select-none">
        <span>⚠️</span>
        <span><strong>No Models Registered:</strong> Scan your drives in Settings or download a model in the Hub.</span>
      </div>
    {/if}

    <!-- Middle Body: MessageList & PersonaPanel scoped strictly between Header and InputBar -->
    <div class="flex-1 flex overflow-hidden relative">
      <MessageList
        {messages}
        onSelectQuickPrompt={populateQuickPrompt}
        onContinueMessage={continueLastMessage}
        onReloadMessages={() => $activeConversationId && loadConversation($activeConversationId)}
      />

      <PersonaPanel {isStreaming} bind:isOpen={isPersonaPanelOpen} />

      {#if !isPersonaPanelOpen}
        <button
          type="button"
          on:click={() => (isPersonaPanelOpen = true)}
          class="absolute right-0 top-1/2 -translate-y-1/2 bg-[var(--bg-card)] border-l border-y border-[var(--border-color)] px-1.5 py-4 rounded-l-xl text-xs text-[var(--text-muted)] hover:text-indigo-400 hover:bg-[var(--bg-base)] shadow-lg transition flex flex-col items-center gap-1 z-10"
          title="Open Persona Profile"
        >
          <span>👤</span>
          <span class="text-[9px] font-mono [writing-mode:vertical-lr]">PERSONA</span>
        </button>
      {/if}
    </div>

    <InputBar
      {isStreaming}
      onSendMessage={handleSend}
      onStopGeneration={stopGeneration}
    />
  </div>
</div>