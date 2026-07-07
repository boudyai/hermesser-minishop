<script lang="ts">
  type Props = {
    description?: string;
    title?: string;
  };

  let { title = "", description = "" }: Props = $props();
</script>

<div class="admin-dashboard-section-head">
  <h3>{title}</h3>
  {#if description}
    <small>{description}</small>
  {/if}
</div>
