import type { ButtonHTMLAttributes } from "react";
import { buttonClasses, type ButtonSize, type ButtonVariant } from "./tokens";

// The shared Button hierarchy: primary (the one action you want taken),
// secondary (an alternative action), subtle (low-emphasis/inline), and
// destructive (delete/cancel). Anything that needs the same look on a
// react-router `<Link>` instead of a `<button>` uses `buttonClasses()`
// directly (see design/tokens.ts) rather than duplicating these rules.

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <button className={`${buttonClasses(variant, size)} ${className}`} {...props} />;
}
