import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { makeStyles, mergeClasses, shorthands } from '@griffel/react';
import Dashboard from './pages/Dashboard';
import Decks from './pages/Decks';
import DeckView from './pages/DeckView';
import Collection from './pages/Collection';
import Cardmarket from './pages/Cardmarket';
import Settings from './pages/Settings';
import Duplicates from './pages/Duplicates';
import Wishlist from './pages/Wishlist';
import { t } from './i18n';
import { sothera, ACCENTS, type AccentName } from './theme/sothera';
import { useAccent } from './main';
import { Sigil, BackdropFX } from './components/sothera';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    position: 'relative',
    zIndex: 1,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    paddingBottom: '18px',
    marginBottom: '0',
    borderBottom: `1px solid ${sothera.glassBorder}`,
    position: 'relative',
    gap: '14px',
    padding: '16px 24px',
    flexWrap: 'wrap',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  brandName: {
    fontFamily: sothera.fontDisplay,
    fontSize: '15px',
    fontWeight: 700,
    letterSpacing: '2.5px',
    color: sothera.fg,
    textTransform: 'uppercase',
  },
  status: {
    paddingLeft: '14px',
    borderLeft: `1px solid ${sothera.glassBorder}`,
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1.5px',
    color: sothera.fgFaint,
    '@media (max-width: 768px)': {
      display: 'none',
    },
  },
  nav: {
    marginLeft: 'auto',
    display: 'flex',
    gap: '4px',
    flexWrap: 'wrap',
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '8px 11px',
    cursor: 'pointer',
    fontFamily: sothera.fontDisplay,
    fontSize: '11px',
    letterSpacing: '1px',
    fontWeight: 500,
    textTransform: 'uppercase',
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor('transparent'),
    transitionProperty: 'all',
    transitionDuration: '140ms',
    backgroundColor: 'transparent',
    '@media (max-width: 768px)': {
      padding: '6px 8px',
      fontSize: '10px',
    },
  },
  navGlyph: {
    fontSize: '11px',
  },
  content: {
    flex: 1,
    overflow: 'auto',
    padding: '16px 24px',
    position: 'relative',
    zIndex: 1,
  },
  accentPicker: {
    display: 'flex',
    gap: '4px',
    alignItems: 'center',
    marginLeft: '8px',
    paddingLeft: '8px',
    borderLeft: `1px solid ${sothera.glassBorder}`,
  },
  accentDot: {
    width: '10px',
    height: '10px',
    borderRadius: '1px',
    cursor: 'pointer',
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    transitionProperty: 'transform',
    transitionDuration: '140ms',
    ':hover': {
      transform: 'scale(1.3)',
    },
  },
});

const navItems = [
  { id: '/', label: t('nav.dashboard'), glyph: '◇' },
  { id: '/decks', label: t('nav.decks'), glyph: '⌬' },
  { id: '/collection', label: t('nav.collection'), glyph: '☷' },
  { id: '/duplicates', label: t('nav.duplicates'), glyph: '◫' },
  { id: '/cardmarket', label: t('nav.cardmarket'), glyph: '⌖' },
  { id: '/wishlist', label: t('nav.wishlist'), glyph: '✧' },
  { id: '/settings', label: t('nav.settings'), glyph: '↯' },
];

export default function App() {
  const styles = useStyles();
  const navigate = useNavigate();
  const location = useLocation();
  const { accent, accentName, setAccent } = useAccent();

  const isActive = (id: string) =>
    location.pathname === id ||
    (id !== '/' && location.pathname.startsWith(id));

  return (
    <>
      <BackdropFX accent={accent} />
      <div className={styles.root}>
        <div className={styles.header}>
          <div className={styles.brand}>
            <Sigil size={18} color={accent.oklch} />
            <div className={styles.brandName}>
              STELLAR<span style={{ color: accent.oklch }}>·</span>VAULT
            </div>
          </div>

          <div className={styles.status}>
            SOTHERA·NODE · {new Date().getFullYear()}.{String(new Date().getMonth() + 1).padStart(2, '0')}.{String(new Date().getDate()).padStart(2, '0')} ·{' '}
            <span style={{ color: sothera.positive }}>● ONLINE</span>
          </div>

          <div className={styles.nav}>
            {navItems.map(item => {
              const active = isActive(item.id);
              return (
                <div
                  key={item.id}
                  className={styles.navItem}
                  onClick={() => navigate(item.id)}
                  style={{
                    color: active ? sothera.fg : sothera.fgFaint,
                    backgroundColor: active ? accent.soft : undefined,
                    borderColor: active ? accent.oklch : undefined,
                  }}
                >
                  <span
                    className={styles.navGlyph}
                    style={{ color: active ? accent.oklch : sothera.fgFainter }}
                  >
                    {item.glyph}
                  </span>
                  {item.label}
                </div>
              );
            })}
          </div>

          <div className={styles.accentPicker}>
            {(Object.entries(ACCENTS) as [AccentName, typeof accent][]).map(([name, a]) => (
              <div
                key={name}
                className={styles.accentDot}
                title={a.label}
                onClick={() => setAccent(name)}
                style={{
                  backgroundColor: a.hex,
                  borderColor: name === accentName ? sothera.fg : 'transparent',
                  transform: name === accentName ? 'scale(1.3)' : undefined,
                }}
              />
            ))}
          </div>
        </div>

        <div className={styles.content}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/decks" element={<Decks />} />
            <Route path="/decks/:id" element={<DeckView />} />
            <Route path="/collection" element={<Collection />} />
            <Route path="/duplicates" element={<Duplicates />} />
            <Route path="/cardmarket" element={<Cardmarket />} />
            <Route path="/wishlist" element={<Wishlist />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </div>
    </>
  );
}
