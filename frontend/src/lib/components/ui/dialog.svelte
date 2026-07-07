<script lang="ts">
  import { X } from "$components/ui/icons.js";
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";
  import { cubicOut } from "svelte/easing";
  import { prefersReducedMotion } from "svelte/motion";
  import { fade, fly } from "svelte/transition";
  import Button from "./button.svelte";
  import ScrollArea from "./scroll-area.svelte";

  type FadeParams = Parameters<typeof fade>[1];
  type FlyParams = Parameters<typeof fly>[1];

  type Props = {
    open?: boolean;
    title?: string;
    description?: string;
    closeLabel?: string;
    onclose?: () => void;
    class?: string;
    titleIcon?: Snippet;
    children?: Snippet;
  };

  let {
    open = false,
    title = "",
    description = "",
    closeLabel = "Close",
    onclose = () => {},
    class: className = "",
    titleIcon,
    children,
  }: Props = $props();

  function backdropTransition(): FadeParams {
    return prefersReducedMotion.current ? { duration: 0 } : { duration: 200 };
  }

  function cardIn(): FlyParams {
    return prefersReducedMotion.current
      ? { duration: 0, y: 0 }
      : { duration: 260, y: 16, easing: cubicOut };
  }

  function cardOut(): FlyParams {
    return prefersReducedMotion.current
      ? { duration: 0, y: 0 }
      : { duration: 200, y: 10, easing: cubicOut };
  }

  function stopScrollPropagation(event: WheelEvent | TouchEvent) {
    event.stopPropagation();
    if (event.target instanceof Element && event.target.closest(".dialog-body-scroll")) return;
    event.preventDefault();
  }

  function readScrollLockCount(body: HTMLElement): number {
    const count = Number(body.dataset.dialogScrollLockCount || "0");
    return Number.isFinite(count) ? count : 0;
  }

  function lockBodyScroll(): () => void {
    if (typeof document === "undefined") return () => {};
    const { body } = document;
    const count = readScrollLockCount(body);
    if (count === 0) {
      body.dataset.dialogPreviousOverflow = body.style.overflow;
      body.style.overflow = "hidden";
    }
    body.dataset.dialogScrollLockCount = String(count + 1);

    return () => {
      const nextCount = Math.max(0, readScrollLockCount(body) - 1);
      if (nextCount > 0) {
        body.dataset.dialogScrollLockCount = String(nextCount);
        return;
      }
      body.style.overflow = body.dataset.dialogPreviousOverflow || "";
      delete body.dataset.dialogPreviousOverflow;
      delete body.dataset.dialogScrollLockCount;
    };
  }

  $effect(() => {
    if (!open) return;
    return lockBodyScroll();
  });
</script>

{#if open}
  <div
    class="dialog"
    role="dialog"
    aria-modal="true"
    aria-label={title}
    tabindex="-1"
    onwheel={stopScrollPropagation}
    ontouchmove={stopScrollPropagation}
  >
    <button
      class="dialog-backdrop"
      type="button"
      aria-label={closeLabel}
      onclick={onclose}
      in:fade={backdropTransition()}
      out:fade={backdropTransition()}
    ></button>
    <section class={cn("dialog-card", className)} in:fly={cardIn()} out:fly={cardOut()}>
      <div class="dialog-head">
        <div class:dialog-title-with-icon={titleIcon} class="dialog-title-block">
          {#if titleIcon}
            <span class="dialog-title-icon" aria-hidden="true">
              {@render titleIcon()}
            </span>
          {/if}
          <div class="dialog-title-copy">
            {#if title}<h2>{title}</h2>{/if}
            {#if description}<p>{description}</p>{/if}
          </div>
        </div>
        <Button variant="icon" size="icon" onclick={onclose} aria-label={closeLabel}>
          <X size={18} />
        </Button>
      </div>
      <ScrollArea class="dialog-body-scroll scroll-area--dialog" maxHeight="none">
        {@render children?.()}
      </ScrollArea>
    </section>
  </div>
{/if}
