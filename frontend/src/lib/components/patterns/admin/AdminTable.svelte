<script lang="ts">
  import { cn } from "$lib/utils.js";
  import type { Snippet } from "svelte";
  import type { HTMLTableAttributes } from "svelte/elements";

  type Props = Omit<HTMLTableAttributes, "children" | "class"> & {
    children?: Snippet;
    class?: string;
    skeleton?: boolean;
  };

  let { skeleton = false, class: className = "", children, ...restProps }: Props = $props();
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
