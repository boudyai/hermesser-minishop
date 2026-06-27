<script>
  import { Label } from "$components/ui/primitives.js";

  let { label = "", hint = "", children } = $props();
</script>

<Label.Root class="admin-field-label">
  {#if label}
    <span>{label}</span>
  {/if}
  {#if hint}
    <small>{hint}</small>
  {/if}
  {@render children?.()}
</Label.Root>
