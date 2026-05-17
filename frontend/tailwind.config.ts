import type { Config } from 'tailwindcss'
import tailwindcssAnimate from 'tailwindcss-animate'

const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        status: {
          running: 'hsl(205 96% 57%)',
          completed: 'hsl(148 66% 48%)',
          waiting: 'hsl(42 93% 56%)',
          rejected: 'hsl(0 72% 56%)',
          degraded: 'hsl(26 91% 56%)',
          failed: 'hsl(0 72% 56%)',
          disconnected: 'hsl(215 12% 48%)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        label: ['12px', { lineHeight: '1.33' }],
        body: ['14px', { lineHeight: '1.5' }],
        heading: ['16px', { lineHeight: '1.25' }],
        display: ['20px', { lineHeight: '1.2' }],
      },
      borderRadius: {
        lg: '8px',
        md: '6px',
        sm: '4px',
      },
    },
  },
  plugins: [tailwindcssAnimate],
}

export default config
