import { ButtonHTMLAttributes, forwardRef } from 'react'

/**
 * Button primitive. Renders a <button> with consistent base styles.
 *
 * Variants map to CSS classes in index.css:
 *   default  - neutral button with border
 *   primary  - filled CTA
 *   ghost    - borderless, for icon bars
 *   danger   - subtle red hover, for destructive actions
 *
 * Shape:
 *   default  - padded rectangle
 *   icon     - 32x32 square, no label
 *   pill     - compact tab-like button (e.g. Text module op selector)
 *
 * `active` renders `.is-active` styling (opt-in, does not clash with :active).
 */
export type ButtonVariant = 'default' | 'primary' | 'ghost' | 'danger'
export type ButtonShape = 'default' | 'icon' | 'pill'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  shape?: ButtonShape
  active?: boolean
}

function classes(...parts: Array<string | false | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'default', shape = 'default', active, className, type, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type ?? 'button'}
      className={classes(
        'btn',
        variant !== 'default' && `btn--${variant}`,
        shape !== 'default' && `btn--${shape}`,
        active && 'is-active',
        className,
      )}
      {...rest}
    />
  )
})
