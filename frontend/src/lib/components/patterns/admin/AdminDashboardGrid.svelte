<script>
  import { cn } from "$lib/utils.js";

  let { columns = 1, class: className = "", children, ...restProps } = $props();
</script>

<div
  class={cn("admin-cn-dashboard-grid", columns === 3 && "admin-cn-dashboard-grid--3", className)}
  {...restProps}
>
  {@render children?.()}
</div>
