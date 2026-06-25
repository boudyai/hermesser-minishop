<script>
  import { cn } from "$lib/utils.js";

  let { skeleton = false, class: className = "", children, ...restProps } = $props();
</script>

<div class="admin-table-wrap">
  <table
    class={cn("admin-table", skeleton && "admin-table-skeleton", className)}
    aria-hidden={skeleton ? "true" : undefined}
    {...restProps}
  >
    {@render children?.()}
  </table>
</div>
