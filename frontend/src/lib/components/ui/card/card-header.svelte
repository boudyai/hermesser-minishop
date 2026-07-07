<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  type Props = Omit<HTMLAttributes<HTMLDivElement>, "class" | "children"> & {
    class?: string;
    children?: Snippet;
  };

  let { class: className = "", children, ...rest }: Props = $props();
</script>

<div data-slot="card-header" class={cn("admin-cn-card-header", className)} {...rest}>
  {@render children?.()}
</div>
