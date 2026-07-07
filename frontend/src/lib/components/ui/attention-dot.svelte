<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { HTMLAttributes } from "svelte/elements";

  type Props = Omit<HTMLAttributes<HTMLSpanElement>, "class"> & {
    class?: string;
    position?: "absolute" | "inline";
  };

  let { position = "absolute", class: className = "", ...rest }: Props = $props();
</script>

<span
  data-slot="attention-dot"
  aria-hidden="true"
  class={cn("attention-dot", position === "inline" && "attention-dot-inline", className)}
  {...rest}
></span>
