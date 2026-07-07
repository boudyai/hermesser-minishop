<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { HTMLAttributes } from "svelte/elements";

  type Props = Omit<HTMLAttributes<HTMLDivElement>, "class"> & {
    class?: string;
    label?: string;
    value?: number | string;
  };

  let { value = 0, label = "", class: className = "", ...rest }: Props = $props();

  const clamped = $derived(Math.max(0, Math.min(100, Number(value) || 0)));
</script>

<div
  class={cn("progress", className)}
  role={label ? "progressbar" : undefined}
  aria-label={label || undefined}
  aria-valuemin={label ? 0 : undefined}
  aria-valuemax={label ? 100 : undefined}
  aria-valuenow={label ? Math.round(clamped) : undefined}
  {...rest}
>
  <span style={`width: ${clamped}%`}></span>
</div>
