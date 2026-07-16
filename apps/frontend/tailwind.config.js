/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        tnvs: {
          black: '#000000',
          void: '#07070D',
          surface: '#0D0D1A',
          surface2: '#14142A',
          border: 'rgba(255,255,255,0.08)',
          borderHi: 'rgba(255,255,255,0.16)',
          muted: '#A1A1AA',
          dim: '#71717A',
          cyan: '#00E5FF',
          blue: '#3B82F6',
          purple: '#8B5CF6',
          pink: '#F472B6',
          win: '#22C55E',
          loss: '#EF4444',
          warn: '#F59E0B',
        },
      },
      fontFamily: {
        sans: ['Chakra Petch', 'Inter', 'system-ui', 'sans-serif'],
        pixel: ['Press Start 2P', 'monospace'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      backgroundImage: {
        'tnvs-glow':
          'linear-gradient(135deg, #00E5FF, #8B5CF6, #F472B6)',
        'tnvs-radial':
          'radial-gradient(ellipse 80% 60% at 50% -20%, rgba(0,229,255,0.08), transparent)',
        'tnvs-radial-r':
          'radial-gradient(ellipse 80% 60% at 50% 120%, rgba(139,92,246,0.08), transparent)',
      },
      boxShadow: {
        'tnvs-glow': '0 0 28px 0 rgba(0,229,255,0.30)',
        'tnvs-soft': '0 10px 40px -10px rgba(139,92,246,0.20)',
        'tnvs-strong': '0 0 60px -10px rgba(139,92,246,0.50)',
      },
      animation: {
        'fade-in': 'fadeIn 280ms ease-out',
        'gradient-x': 'gradientX 6s ease infinite',
        'pulse-slow': 'pulseSlow 2.6s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        gradientX: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        pulseSlow: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
