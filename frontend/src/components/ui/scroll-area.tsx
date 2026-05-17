import * as React from 'react'
import { cn } from '@/lib/utils'

export type ScrollAreaProps = React.HTMLAttributes<HTMLDivElement>

export const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('overflow-y-auto overscroll-contain [scrollbar-width:thin]', className)}
      {...props}
    />
  ),
)

ScrollArea.displayName = 'ScrollArea'
