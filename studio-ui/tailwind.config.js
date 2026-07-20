export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#070b16', panel: '#0e1626', line: '#1c2841',
        teal: '#39d2c0', purple: '#bc8cff', coral: '#ff8c66',
        amber: '#e3b341', mut: '#8697b8',
      },
      keyframes: {
        'border-beam': { '100%': { 'offset-distance': '100%' } },
        shine: { '0%':{'background-position':'0% 0%'}, '50%':{'background-position':'100% 100%'}, to:{'background-position':'0% 0%'} },
        rise: { from:{opacity:'0',transform:'translateY(8px)'}, to:{opacity:'1',transform:'none'} },
      },
      animation: {
        'border-beam': 'border-beam calc(var(--duration)*1s) infinite linear',
        shine: 'shine var(--duration) infinite linear',
        rise: 'rise .3s ease',
      },
    },
  },
}
