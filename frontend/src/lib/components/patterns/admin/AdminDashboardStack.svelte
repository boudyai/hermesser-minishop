<script>
  import { cn } from "$lib/utils.js";

  let { class: className = "", children, ...restProps } = $props();
</script>

<div class={cn("admin-cn-dashboard-stack", className)} {...restProps}>
  {@render children?.()}
</div>
