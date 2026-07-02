<script lang="ts">
  import type { Snippet } from "svelte";

  type Props = {
    number?: string;
    label?: string;
    wide?: boolean;
    children?: Snippet;
  };

  let { number = "", label = "", wide = false, children }: Props = $props();
</script>

<section class:wide class="preview-phone-wrap">
  <h2><span>{number}.</span> {label}</h2>
  <div class="preview-phone">
    {@render children?.()}
  </div>
</section>
