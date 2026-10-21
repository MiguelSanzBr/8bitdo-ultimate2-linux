// Ícones em SVG inline; os das categorias são os mesmos traços do app desktop.
import type { ReactNode } from 'react'

function Icon({ children, box = '-16 -16 32 32' }: { children: ReactNode; box?: string }) {
  return <svg className="icon" viewBox={box} aria-hidden="true">{children}</svg>
}

export const ICONS = {
  buttons: <Icon>{[[0, -9], [0, 9], [-9, 0], [9, 0]].map(([x, y]) => <circle key={`${x},${y}`} cx={x} cy={y} r={4} />)}</Icon>,
  sticks: <Icon>{[13, 7, 2].map((r) => <circle key={r} r={r} />)}</Icon>,
  triggers: <Icon><rect x={-9} y={-13} width={18} height={26} rx={8} /><path d="M-9 -2H9" /></Icon>,
  leds: (
    <Icon>
      <circle r={6} />
      <path d={[0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
        const [c, s] = [Math.cos((a * Math.PI) / 180), Math.sin((a * Math.PI) / 180)]
        return `M${(c * 9).toFixed(1)} ${(s * 9).toFixed(1)}L${(c * 13).toFixed(1)} ${(s * 13).toFixed(1)}`
      }).join('')} />
    </Icon>
  ),
  profile: <Icon><circle cy={-8} r={5} /><path d="M-11 10A11 11 0 0 1 11 10" /></Icon>,
  theme: <Icon box="0 0 24 24"><circle cx={12} cy={12} r={8.5} /><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="currentColor" /></Icon>,
  download: <Icon box="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></Icon>,
  reload: <Icon box="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" /></Icon>,
  power: <Icon box="0 0 24 24"><path d="M12 3v9M7 6.3a7 7 0 1 0 10 0" /></Icon>,
  link: <Icon box="0 0 24 24"><path d="M9 7H7a5 5 0 0 0 0 10h2M15 7h2a5 5 0 0 1 0 10h-2M8 12h8" /></Icon>,
  flask: <Icon box="0 0 24 24"><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3M7.5 15h9" /></Icon>,
  alert: <Icon box="0 0 24 24"><path d="M12 3 2 20h20L12 3zM12 10v4M12 17v.5" /></Icon>,
  arrow: <Icon box="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></Icon>,
}
