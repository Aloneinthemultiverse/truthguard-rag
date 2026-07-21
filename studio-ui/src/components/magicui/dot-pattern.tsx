import { useId } from 'react'
import { cn } from '@/lib/utils'
export function DotPattern({ width=18, height=18, cx=1, cy=1, cr=1, className }: any) {
  const id = useId()
  return (
    <svg aria-hidden className={cn('pointer-events-none absolute inset-0 h-full w-full fill-white/[0.09]', className)}>
      <defs><pattern id={id} width={width} height={height} patternUnits="userSpaceOnUse" patternContentUnits="userSpaceOnUse">
        <circle id="pattern-circle" cx={cx} cy={cy} r={cr}/>
      </pattern></defs>
      <rect width="100%" height="100%" strokeWidth={0} fill={`url(#${id})`}/>
    </svg>)
}
