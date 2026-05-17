import * as React from 'react'
import { cn } from '@/lib/utils'

interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
  onValueChange: (value: string) => void
}

export function Tabs({ value, onValueChange, ...props }: TabsProps) {
  void value
  void onValueChange
  return <div {...props} />
}

export function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex border-b border-border', className)} {...props} />
}

interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
  activeValue: string
  onValueChange: (value: string) => void
}

export function TabsTrigger({
  className,
  value,
  activeValue,
  onValueChange,
  type = 'button',
  ...props
}: TabsTriggerProps) {
  const active = value === activeValue
  return (
    <button
      type={type}
      className={cn(
        'min-h-10 border-b-2 px-3 text-label transition-colors',
        active
          ? 'border-primary text-primary'
          : 'border-transparent text-muted-foreground hover:text-foreground',
        className,
      )}
      onClick={() => onValueChange(value)}
      {...props}
    />
  )
}

interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
  activeValue: string
}

export function TabsContent({ className, value, activeValue, ...props }: TabsContentProps) {
  if (value !== activeValue) return null
  return <div className={cn('min-h-0', className)} {...props} />
}
