<script>
  import { cn } from "$lib/utils.js";

  let { variant = "muted", class: className = "", children, ...restProps } = $props();
</script>

<span
  class={cn(
    "admin-badge",
    variant === "success" && "admin-badge-success",
    variant === "danger" && "admin-badge-danger",
    variant === "warning" && "admin-badge-warning",
    variant === "muted" && "admin-badge-muted",
    className
  )}
  {...restProps}
>
  {@render children?.()}
</span>
