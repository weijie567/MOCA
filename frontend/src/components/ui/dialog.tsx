import * as React from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <div className="absolute inset-0" onClick={() => onOpenChange(false)} aria-hidden="true" />
      {children}
    </div>
  )
}

export function DialogContent({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className={cn('relative z-10 w-full max-w-md rounded-lg border border-border bg-card shadow-xl', className)}
      {...props}
    >
      {children}
    </div>
  )
}

export function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('border-b border-border px-4 py-3', className)} {...props} />
}

export function DialogTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn('text-heading font-semibold', className)} {...props} />
}

export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex justify-end gap-2 px-4 py-3', className)} {...props} />
}

interface DialogCloseProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  onOpenChange: (open: boolean) => void
}

export function DialogClose({ className, onOpenChange, type = 'button', ...props }: DialogCloseProps) {
  return (
    <Button
      type={type}
      variant="ghost"
      className={cn('absolute right-2 top-2 h-8 w-8 p-0', className)}
      onClick={() => onOpenChange(false)}
      {...props}
    >
      <X className="h-4 w-4" aria-hidden="true" />
      <span className="sr-only">Close</span>
    </Button>
  )
}
