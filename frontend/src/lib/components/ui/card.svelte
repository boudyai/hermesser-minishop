<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  type Props = Omit<HTMLAttributes<HTMLElement>, "class" | "children"> & {
    active?: boolean;
    compact?: boolean;
    class?: string;
    children?: Snippet;
  };

  let {
    active = false,
    compact = false,
    class: className = "",
    children,
    ...rest
  }: Props = $props();
</script>

<section
  class={cn("card", active && "card-active", compact && "card-compact", className)}
  {...rest}
>
  {@render children?.()}
</section>
