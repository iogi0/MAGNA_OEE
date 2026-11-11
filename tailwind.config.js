/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        citycare: {
          lightBg: "#F3F6F9",
          darkBase: "#09090B",
          darkCard: "#18181B",
          darkCardBorder: "#27272A",
          darkSlate: "#111827",
          subGray: "#6B7280",
          neonGreen: "#10B981",
          neonOrange: "#F59E0B",
          neonBlue: "#3B82F6",
          neonRed: "#EF4444",
          magnaRed: "#E53935",
        }
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'white-card': '0px 4px 24px rgba(0, 0, 0, 0.04)',
        'white-card-hover': '0px 12px 32px rgba(0, 0, 0, 0.08)',
        'glow-green': '0 0 24px rgba(16, 185, 129, 0.25), inset 0 1px 0 rgba(16, 185, 129, 0.3)',
        'glow-orange': '0 0 24px rgba(245, 158, 11, 0.25), inset 0 1px 0 rgba(245, 158, 11, 0.3)',
        'glow-blue': '0 0 24px rgba(59, 130, 246, 0.25), inset 0 1px 0 rgba(59, 130, 246, 0.3)',
        'glow-red': '0 0 24px rgba(239, 68, 68, 0.25), inset 0 1px 0 rgba(239, 68, 68, 0.3)',
      },
      borderRadius: {
        '24': '24px',
        '28': '28px',
        '32': '32px',
        '40': '40px',
      }
    },
  },
  plugins: [],
}
