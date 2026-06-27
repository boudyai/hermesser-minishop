<script>
  import { cva } from "class-variance-authority";
  import { cn } from "$lib/utils.js";

  let {
    type = "button",
    variant = "default",
    size = "default",
    disabled = false,
    onclick = undefined,
    class: className = "",
    children,
    ...restProps
  } = $props();

  const buttonVariants = cva("admin-btn", {
    variants: {
      variant: {
        default: "",
        primary: "admin-btn-primary",
        ghost: "admin-btn-ghost",
        danger: "admin-btn-danger",
        dangerSoft: "admin-btn-danger-soft",
        icon: "admin-btn-icon",
      },
      size: {
        default: "",
        sm: "admin-btn-sm",
        icon: "admin-btn-icon",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  });
</script>

<button
  class={cn(buttonVariants({ variant, size }), className)}
  {type}
  {disabled}
  {onclick}
  {...restProps}
>
  {@render children?.()}
</button>
