<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  type BadgeVariant = "default" | "destructive" | "muted" | "outline" | "success";
  type Props = Omit<HTMLAttributes<HTMLSpanElement>, "class" | "children"> & {
    children?: Snippet;
    class?: string;
    variant?: BadgeVariant;
  };

  let { variant = "default", class: className = "", children, ...rest }: Props = $props();
</script>

<span
  data-slot="badge"
  class={cn(
    "admin-cn-badge",
    variant === "outline" && "admin-cn-badge-outline",
    variant === "destructive" && "admin-cn-badge-destructive",
    variant === "success" && "admin-cn-badge-success",
    variant === "muted" && "admin-cn-badge-muted",
    className
  )}
  {...rest}
>
  {@render children?.()}
</span>
