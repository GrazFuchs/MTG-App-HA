import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Button, Spinner } from '@fluentui/react-components';
import { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react';
import { makeStyles, mergeClasses, shorthands } from '@griffel/react';
// Lazily loaded, one chunk per page. The build was a single 1.15 MB bundle:
// opening the dashboard also downloaded the deck comparison, the Cardmarket
// import and the markdown renderer, which is felt over the cloudflared tunnel.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Decks = lazy(() => import('./pages/Decks'));
const DeckView = lazy(() => import('./pages/DeckView'));
const DeckCompare = lazy(() => import('./pages/DeckCompare'));
const Collection = lazy(() => import('./pages/Collection'));
const Inbox = lazy(() => import('./pages/Inbox'));
const Cardmarket = lazy(() => import('./pages/Cardmarket'));
const Settings = lazy(() => import('./pages/Settings'));
const Duplicates = lazy(() => import('./pages/Duplicates'));
const Wishlist = lazy(() => import('./pages/Wishlist'));
import { api } from './api';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ErrorBanner } from './components/ErrorBanner';
import { NotFound } from './pages/NotFound';
import { t } from './i18n';
import { sothera, ACCENTS, ACCENTS_LIGHT, type AccentName } from './theme/sothera';
import { useAccent } from './main';
import { useSotheraTheme } from './theme';
import { Sigil, BackdropFX } from './components/sothera';
import BackToTop from './components/BackToTop';

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
  skipLink: {
    position: 'absolute',
    left: '-9999px',
    top: 0,
    zIndex: 100,
    padding: '8px 14px',
    backgroundColor: sothera.bg,
    color: sothera.fg,
    fontFamily: sothera.fontDisplay,
    fontSize: '12px',
    ':focus': {
      left: '8px',
      top: '8px',
    },
  },
  navItem: {
    // The nav items are anchors now (see the render site); without these two
    // an <a> arrives underlined and in the browser's link colour.
    textDecoration: 'none',
    color: 'inherit',
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
    // A <button> now, so the browser's default padding and background have to
    // go — but the focus ring stays: these dots are the only way to change the
    // accent, and a keyboard user has to be able to see which one is focused.
    padding: 0,
    backgroundColor: 'transparent',
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
  themePicker: {
    display: 'flex',
    gap: '2px',
    alignItems: 'center',
    marginLeft: '8px',
    paddingLeft: '8px',
    borderLeft: `1px solid ${sothera.glassBorder}`,
  },
  themeBtn: {
    padding: '4px 7px',
    fontSize: '9px',
    fontFamily: sothera.fontMono,
    letterSpacing: '1px',
    textTransform: 'uppercase',
    cursor: 'pointer',
    background: 'transparent',
    color: sothera.fgFaint,
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor('transparent'),
    transitionProperty: 'color, border-color',
    transitionDuration: '140ms',
    ':hover': {
      color: sothera.fgMuted,
    },
  },
});

const navItems = [
  { id: '/', label: t('nav.dashboard'), glyph: '◇' },
  { id: '/decks', label: t('nav.decks'), glyph: '⌬' },
  { id: '/collection', label: t('nav.collection'), glyph: '☷' },
  { id: '/inbox', label: t('nav.inbox'), glyph: '⊕' },
  { id: '/duplicates', label: t('nav.duplicates'), glyph: '◫' },
  { id: '/cardmarket', label: t('nav.cardmarket'), glyph: '⌖' },
  { id: '/wishlist', label: t('nav.wishlist'), glyph: '✧' },
  { id: '/settings', label: t('nav.settings'), glyph: '↯' },
];

export default function App() {
  const styles = useStyles();
  const contentRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const { accent, accentName, setAccent } = useAccent();
  const { mode, setMode, isDark } = useSotheraTheme();
  const displayAccents = isDark ? ACCENTS : ACCENTS_LIGHT;
  const [pendingCount, setPendingCount] = useState(0);

  const fetchPendingCount = useCallback(() => {
    api.getInboxStats()
      .then(s => setPendingCount(s.pending_count))
      .catch(() => {});
  }, []);

  // Poll on tab switch + every 60s + on visibility change
  useEffect(() => {
    fetchPendingCount();
    const interval = setInterval(fetchPendingCount, 60_000);
    const onVisibility = () => {
      if (document.visibilityState === 'visible') fetchPendingCount();
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [fetchPendingCount]);

  // Refetch when navigating
  useEffect(() => {
    fetchPendingCount();
  }, [location.pathname, fetchPendingCount]);

  const isActive = (id: string) =>
    location.pathname === id ||
    (id !== '/' && location.pathname.startsWith(id));

  return (
    <>
      <BackdropFX accent={accent} />
      {/* First tab stop on the page. Eight nav items sit between the top of the
          document and the content; without this a keyboard user walks all of
          them on every single page. Visible only while focused. */}
      <a href="#content" className={styles.skipLink}>{t('nav.skip')}</a>
      <div className={styles.root}>
        <div className={styles.header}>
          <div className={styles.brand}>
            <Sigil size={18} color={accent.oklch} />
            <div className={styles.brandName}>
              MTG<span style={{ color: accent.oklch }}>·</span>{t('app.subtitle')}
            </div>
          </div>

          <div className={styles.status}>
            SOTHERA·NODE · {new Date().getFullYear()}.{String(new Date().getMonth() + 1).padStart(2, '0')}.{String(new Date().getDate()).padStart(2, '0')} ·{' '}
            <span style={{ color: sothera.positive }}>● ONLINE</span>
          </div>

          {/* A <Link>, not a <div onClick>. The nav was unreachable by keyboard
              entirely — no tab stop, no Enter, nothing for a screen reader to
              announce as a link — and middle-click/open-in-new-tab did nothing
              either, because there was no href to open. */}
          <nav className={styles.nav} aria-label={t('nav.primary')}>
            {navItems.map(item => {
              const active = isActive(item.id);
              return (
                <Link
                  key={item.id}
                  to={item.id}
                  className={styles.navItem}
                  aria-current={active ? 'page' : undefined}
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
                  {item.id === '/inbox' && pendingCount > 0 && (
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      minWidth: '16px',
                      height: '16px',
                      padding: '0 4px',
                      borderRadius: '2px',
                      backgroundColor: accent.oklch,
                      color: '#000',
                      fontSize: '9px',
                      fontFamily: sothera.fontMono,
                      fontWeight: 700,
                      letterSpacing: 0,
                      lineHeight: 1,
                    }}>
                      {pendingCount}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          <div className={styles.accentPicker} role="group" aria-label={t('nav.accent')}>
            {(Object.entries(displayAccents) as [AccentName, typeof accent][]).map(([name, a]) => (
              <button
                key={name}
                type="button"
                className={styles.accentDot}
                title={a.label}
                aria-label={a.label}
                aria-pressed={name === accentName}
                onClick={() => setAccent(name)}
                style={{
                  backgroundColor: a.hex,
                  borderColor: name === accentName ? sothera.fg : 'transparent',
                  transform: name === accentName ? 'scale(1.3)' : undefined,
                }}
              />
            ))}
          </div>

          <div className={styles.themePicker}>
            {(['auto', 'dark', 'light'] as const).map(m => (
              <button
                key={m}
                className={styles.themeBtn}
                onClick={() => setMode(m)}
                aria-pressed={mode === m}
                aria-label={`Theme: ${m}`}
                style={mode === m ? { color: accent.oklch, borderColor: accent.oklch } : undefined}
              >
                {m === 'auto' ? '◎' : m === 'dark' ? '◑' : '○'}
              </button>
            ))}
          </div>
        </div>

        <main id="content" className={styles.content} ref={contentRef}>
          {/* One boundary around every page: a component that throws used to
              blank the content area with no hint that anything had failed. */}
          <ErrorBoundary
            fallback={(err, retry) => (
              <ErrorBanner
                title={t('app.render_failed')}
                message={err.message}
                action={<Button size="small" onClick={retry}>{t('common.retry')}</Button>}
              />
            )}
          >
            <Suspense fallback={<Spinner label={t('app.loading')} />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/decks" element={<Decks />} />
                <Route path="/decks/compare" element={<DeckCompare />} />
                <Route path="/decks/:id" element={<DeckView />} />
                <Route path="/collection" element={<Collection />} />
                <Route path="/inbox" element={<Inbox />} />
                <Route path="/duplicates" element={<Duplicates />} />
                <Route path="/cardmarket" element={<Cardmarket />} />
                <Route path="/wishlist" element={<Wishlist />} />
                <Route path="/settings" element={<Settings />} />
                {/* Without this an unknown path rendered an empty content
                    area that reads exactly like a page with no data. */}
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
          <BackToTop scrollRef={contentRef} />
        </main>
      </div>
    </>
  );
}
