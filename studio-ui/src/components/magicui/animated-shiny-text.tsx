import { cn } from '@/lib/utils'
import { CSSProperties } from 'react'
export function AnimatedShinyText({ children, className, shimmerWidth=100 }:{ children:React.ReactNode; className?:string; shimmerWidth?:number }) {
 return (<span style={{ '--sw':`${shimmerWidth}px` } as CSSProperties}
  className={cn('text-mut/70 [background-size:var(--sw)_100%] [background-position:0_0] bg-clip-text bg-no-repeat',
  '[background-image:linear-gradient(110deg,transparent_40%,#e6edf7_50%,transparent_60%)]',
  'animate-[shine_2.5s_infinite]', className)}>{children}</span>)
}
