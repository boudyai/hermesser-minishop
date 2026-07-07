<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  type Props = Omit<HTMLAttributes<HTMLDivElement>, "children" | "class"> & {
    children?: Snippet;
    class?: string;
    tone?: "card" | "default";
  };

  let { tone = "default", class: className = "", children, ...restProps }: Props = $props();
</script>

<div class={cn(tone === "card" ? "admin-card-body" : "admin-empty", className)} {...restProps}>
  {@render children?.()}
</div>
