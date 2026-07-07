<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  type Props = Omit<HTMLAttributes<HTMLParagraphElement>, "class" | "children"> & {
    children?: Snippet;
    class?: string;
    error?: boolean;
  };

  let { error = false, class: className = "", children, ...rest }: Props = $props();
</script>

<p class={cn("status-line", error && "error", className)} {...rest}>
  {@render children?.()}
</p>
