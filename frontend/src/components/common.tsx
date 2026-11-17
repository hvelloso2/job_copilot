import { AlertCircle, Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export function ErrorAlert({ message, title = 'Algo deu errado' }: { message: string; title?: string }) {
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}

/** Spinner with a message: AI calls take several seconds, so always say what is happening. */
export function Loading({ message, className }: { message: string; className?: string }) {
  return (
    <div className={cn('flex items-center gap-2 text-sm text-muted-foreground', className)} role="status">
      <Loader2 className="size-4 animate-spin" />
      {message}
    </div>
  )
}

export function ColorBadge({ className, children }: { className: string; children: ReactNode }) {
  return (
    <Badge variant="outline" className={cn('font-medium', className)}>
      {children}
    </Badge>
  )
}

export function Section({ title, children, description }: { title: string; children: ReactNode; description?: string }) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  )
}
