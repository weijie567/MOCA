import * as React from 'react'
import { cn } from '@/lib/utils'

type BadgeVariant = 'default' | 'secondary' | 'outline' | 'destructive' | 'success' | 'warning'

const variantClasses: Record<BadgeVariant, string> = {
  default: 'border-primary/40 bg-primary/15 text-primary',
  secondary: 'border-border bg-muted text-muted-foreground',
  outline: 'border-border bg-transparent text-foreground',
  destructive: 'border-destructive/50 bg-destructive/15 text-destructive-foreground',
  success: 'border-status-completed/50 bg-status-completed/15 text-status-completed',
  warning: 'border-status-waiting/50 bg-status-waiting/15 text-status-waiting',
}

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-label font-normal',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  )
}
