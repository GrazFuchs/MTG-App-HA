import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import {
  makeStyles,
  tokens,
  TabList,
  Tab,
  Title1,
} from '@fluentui/react-components';
import {
  Home24Regular,
  Collections24Regular,
  Stack24Regular,
  Cart24Regular,
  ArrowSync24Regular,
  CopySelect20Regular,
  Heart24Regular,
} from '@fluentui/react-icons';
import Dashboard from './pages/Dashboard';
import Decks from './pages/Decks';
import DeckView from './pages/DeckView';
import Collection from './pages/Collection';
import Cardmarket from './pages/Cardmarket';
import Settings from './pages/Settings';
import Duplicates from './pages/Duplicates';
import Wishlist from './pages/Wishlist';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    padding: '8px 16px',
    gap: '16px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    flexWrap: 'wrap',
  },
  title: {
    '@media (max-width: 600px)': {
      fontSize: tokens.fontSizeBase400,
    },
  },
  nav: {
    overflowX: 'auto',
  },
  content: {
    flex: 1,
    overflow: 'auto',
    padding: '16px',
  },
});

const tabs = [
  { value: '/', label: 'Dashboard', icon: <Home24Regular /> },
  { value: '/decks', label: 'Decks', icon: <Stack24Regular /> },
  { value: '/collection', label: 'Collection', icon: <Collections24Regular /> },
  { value: '/duplicates', label: 'Duplicates', icon: <CopySelect20Regular /> },
  { value: '/cardmarket', label: 'Cardmarket', icon: <Cart24Regular /> },
  { value: '/wishlist', label: 'Wishlist', icon: <Heart24Regular /> },
  { value: '/settings', label: 'Settings', icon: <ArrowSync24Regular /> },
];

export default function App() {
  const styles = useStyles();
  const navigate = useNavigate();
  const location = useLocation();

  const currentTab = tabs.find(
    (t) =>
      t.value === location.pathname ||
      (t.value !== '/' && location.pathname.startsWith(t.value))
  )?.value ?? '/';

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <Title1 className={styles.title}>MTG Collection</Title1>
        <div className={styles.nav}>
          <TabList
            selectedValue={currentTab}
            onTabSelect={(_, data) => navigate(data.value as string)}
            size="small"
          >
            {tabs.map((t) => (
              <Tab key={t.value} value={t.value} icon={t.icon}>
                {t.label}
              </Tab>
            ))}
          </TabList>
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
  );
}
