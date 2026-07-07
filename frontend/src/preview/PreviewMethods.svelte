<script lang="ts">
  import { CreditCard, Send, WalletCards } from "$components/ui/icons.js";

  type PreviewMethod = { name?: string };
  type Props = {
    methods?: PreviewMethod[];
  };

  let { methods = [] }: Props = $props();

  const icons = [CreditCard, Send, WalletCards, WalletCards];

  function note(index: number): string {
    if (index === 0) return "Visa, Mastercard";
    if (index === 1) return "Быстро и удобно";
    if (index === 2) return "USDT, BTC, ETH";
    return "ЮMoney, СБП и др.";
  }
</script>

<div
  class:method-grid-single={methods.length === 1}
  class:method-grid-many={methods.length > 2}
  class="method-grid"
>
  {#each methods as method, index}
    {@const MethodIcon = icons[index] || WalletCards}
    <div class:active={index === 1} class="method-card">
      <MethodIcon size={18} />
      <span>
        <strong>{method.name}</strong>
        <small>{note(index)}</small>
      </span>
    </div>
  {/each}
</div>
