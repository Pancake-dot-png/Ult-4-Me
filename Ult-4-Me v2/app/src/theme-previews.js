const THEMES = {
  cyberpunk: {
    pink:  { accent: '#ff1f8f', accent2: '#00f0ff', bg: '#07030d', bg2: '#0d0717', ink: '#f4e8ff', label: 'Neon' },
    blue:  { accent: '#1f7fff', accent2: '#ff1f8f', bg: '#03060d', bg2: '#07101a', ink: '#f4e8ff', label: 'Cryo' },
    green: { accent: '#1fd97a', accent2: '#ffe53a', bg: '#03100a', bg2: '#071a12', ink: '#f4e8ff', label: 'MtnDew' },
    blood: { accent: '#dc1432', accent2: '#d8d0cc', bg: '#050203', bg2: '#0c0506', ink: '#e8e0dc', label: 'Blood' },
  },
  plush: {
    blush:  { accent: '#ff7ab8', accent2: '#c9aaf0', bg: '#fff5f9', bg2: '#ffeaf3', ink: '#5a2a4a', label: 'Blush' },
    cotton: { accent: '#7abdff', accent2: '#e8a8c8', bg: '#f1f7ff', bg2: '#e6f0ff', ink: '#2a3a5a', label: 'Cotton' },
    lilac:  { accent: '#b07aff', accent2: '#ffaae0', bg: '#f8f2ff', bg2: '#f0e8ff', ink: '#3a2a5a', label: 'Lilac' },
    butter: { accent: '#efd442', accent2: '#965f37', bg: '#fffbf0', bg2: '#fff5e0', ink: '#5a4a2a', label: 'Daisy' },
  },
  discord: {
    dark: {accent:'#5865f2',accent2:'#b7beff',bg:'#313338',bg2:'#2b2d31',ink:'#f2f3f5',label:'Dark',dark:true},
    light: {accent:'#5865f2',accent2:'#b7beff',bg:'#ffffff',bg2:'#f2f3f5',ink:'#2e3338',label:'Light'},
  },
};

function readThemeColors(saved = {}) {
  const colors = {};
  for (const [family, palette] of Object.entries(THEMES)) {
    colors[family] = Object.hasOwn(palette, saved?.[family]) ? saved[family] : Object.keys(palette)[0];
  }
  return colors;
}

function styleThemePreview(element, family, tint) {
  const theme = THEMES[family][tint];
  element.style.setProperty('--choice-accent', theme.accent);
  element.style.setProperty('--preview-ink', theme.ink);
  element.style.setProperty('--preview-line', family === 'discord'
    ? (tint === 'light' ? '#d8dadd' : '#41434a') : theme.accent);
  if (family === 'plush') {
    element.style.background = `linear-gradient(110deg,${theme.bg},color-mix(in srgb,${theme.accent} 18%,${theme.bg2}))`;
    element.style.boxShadow = `0 4px 0 color-mix(in srgb,${theme.accent} 35%,${theme.bg2})`;
  } else {
    element.style.background = family === 'cyberpunk'
      ? `linear-gradient(110deg,${theme.bg},${theme.bg2})` : theme.bg2;
  }
}

module.exports = {THEMES, readThemeColors, styleThemePreview};
