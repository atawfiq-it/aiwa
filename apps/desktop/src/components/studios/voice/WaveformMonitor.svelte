<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  export let isActive: boolean = false;
  export let statusText: string = 'Idle';

  let canvasElement: HTMLCanvasElement;
  let animationFrameId: number | null = null;

  $: if (canvasElement) {
    updateAnimation(isActive);
  }

  function updateAnimation(active: boolean) {
    if (!canvasElement) return;
    const ctx = canvasElement.getContext('2d');
    if (!ctx) return;

    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }

    const width = canvasElement.width;
    const height = canvasElement.height;
    const midY = height / 2;

    if (!active) {
      ctx.clearRect(0, 0, width, height);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = '#334155';
      ctx.beginPath();
      ctx.moveTo(0, midY);
      ctx.lineTo(width, midY);
      ctx.stroke();
      return;
    }

    let step = 0;
    function render() {
      ctx.clearRect(0, 0, width, height);
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#6366f1';
      ctx.beginPath();

      const numPoints = 50;
      const sliceWidth = width / numPoints;
      let x = 0;

      for (let i = 0; i < numPoints; i++) {
        const amplitude = Math.sin(i * 0.35 + step) * 12;
        const y = midY + amplitude;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }

      ctx.stroke();
      step += 0.15;
      animationFrameId = requestAnimationFrame(render);
    }
    render();
  }

  onMount(() => {
    updateAnimation(false);
  });

  onDestroy(() => {
    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId);
    }
  });
</script>

<div class="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-4 flex items-center justify-between shadow-sm select-none">
  <div class="flex items-center gap-3">
    <span class="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">Audio Monitor:</span>
    <span class={`text-[11px] font-mono font-semibold ${isActive ? 'text-[var(--accent)] animate-pulse' : 'text-slate-500'}`}>
      {statusText}
    </span>
  </div>
  <canvas bind:this={canvasElement} width="300" height="36" class="rounded-lg bg-[var(--bg-base)]"></canvas>
</div>
