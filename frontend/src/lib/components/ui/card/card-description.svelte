<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  type Props = Omit<HTMLAttributes<HTMLParagraphElement>, "class" | "children"> & {
    class?: string;
    children?: Snippet;
  };

  let { class: className = "", children, ...rest }: Props = $props();
</script>

<p data-slot="card-description" class={cn("admin-cn-card-description", className)} {...rest}>
  {@render children?.()}
</p>
