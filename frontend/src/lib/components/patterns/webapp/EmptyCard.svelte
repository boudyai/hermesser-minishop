<script lang="ts">
  import Card from "$components/ui/card.svelte";
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";

  type Props = Record<string, unknown> & {
    children?: Snippet;
    class?: string;
  };

  let { class: className = "", children, ...rest }: Props = $props();
</script>

<Card class={cn("empty-card", className)} {...rest}>
  {@render children?.()}
</Card>
