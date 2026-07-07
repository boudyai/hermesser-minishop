<script lang="ts">
  import { Label } from "$components/ui/primitives.js";
  import type { Snippet } from "svelte";

  type Props = {
    children?: Snippet;
    hint?: string;
    label?: string;
  };

  let { label = "", hint = "", children }: Props = $props();
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
