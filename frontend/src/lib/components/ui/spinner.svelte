<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { HTMLAttributes } from "svelte/elements";

  type SpinnerSize = "default" | "sm" | "lg";
  type Props = Omit<HTMLAttributes<HTMLSpanElement>, "class"> & {
    class?: string;
    label?: string;
    size?: SpinnerSize;
  };

  let { size = "default", label = "", class: className = "", ...rest }: Props = $props();
</script>

<span
  class={cn(
    "ui-spinner",
    size === "sm" && "ui-spinner-sm",
    size === "lg" && "ui-spinner-lg",
    className
  )}
  role={label ? "status" : undefined}
  aria-label={label || undefined}
  aria-hidden={label ? undefined : "true"}
  {...rest}
></span>
