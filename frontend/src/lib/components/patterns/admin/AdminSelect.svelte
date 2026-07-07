<script lang="ts">
  import { Check, ChevronDown } from "$components/ui/icons.js";
  import { Select } from "$components/ui/primitives.js";

  type SelectItem = { value: string; label: string };
  type Props = {
    value?: string;
    items?: SelectItem[];
    ariaLabel?: string;
    placeholder?: string;
    disabled?: boolean;
    side?: "bottom" | "left" | "right" | "top";
    align?: "center" | "end" | "start";
    sideOffset?: number;
    collisionPadding?: number;
    onValueChange?: (value: string) => void;
    class?: string;
  };

  let {
    value = $bindable(""),
    items = [],
    ariaLabel = "",
    placeholder = "",
    disabled = false,
    side = "bottom",
    align = "start",
    sideOffset = 6,
    collisionPadding = 12,
    onValueChange = () => {},
    class: className = "",
  }: Props = $props();

  const selected = $derived(items.find((item) => item.value === value));

  function handleValueChange(next: string) {
    value = next;
    onValueChange(next);
  }
</script>

<Select.Root type="single" {value} {items} {disabled} onValueChange={handleValueChange}>
  <Select.Trigger
    class={`admin-select-trigger ${className}`.trim()}
    aria-label={ariaLabel || placeholder}
  >
    <span>{selected?.label || placeholder}</span>
    <ChevronDown size={14} class="admin-select-icon" />
  </Select.Trigger>
  <Select.Portal>
    <Select.Content class="admin-select-content" {side} {align} {sideOffset} {collisionPadding}>
      <Select.Viewport class="admin-select-viewport">
        {#each items as item (item.value)}
          <Select.Item value={item.value} label={item.label} class="admin-select-item">
            <span>{item.label}</span>
            <Check size={14} class="admin-select-item-check" />
          </Select.Item>
        {/each}
      </Select.Viewport>
    </Select.Content>
  </Select.Portal>
</Select.Root>
