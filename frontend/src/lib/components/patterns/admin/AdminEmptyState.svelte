<script>
  import { cn } from "$lib/utils.js";

  let { tone = "default", class: className = "", children, ...restProps } = $props();
</script>

<div class={cn(tone === "card" ? "admin-card-body" : "admin-empty", className)} {...restProps}>
  {@render children?.()}
</div>
