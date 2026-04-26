/**
 * Minimal i18n module. Detects language from browser / HA and provides t() lookup.
 */

const translations: Record<string, Record<string, string>> = {
  en: {
    'nav.dashboard': 'Dashboard',
    'nav.decks': 'Decks',
    'nav.collection': 'Collection',
    'nav.duplicates': 'Duplicates',
    'nav.cardmarket': 'Cardmarket',
    'nav.wishlist': 'Wishlist',
    'nav.settings': 'Settings',
    'dashboard.title': 'Dashboard',
    'dashboard.total_cards': 'Total Cards',
    'dashboard.unique_cards': 'Unique Cards',
    'dashboard.value_eur': 'Collection Value (EUR)',
    'dashboard.value_usd': 'Collection Value (USD)',
    'dashboard.decks': 'Decks',
    'dashboard.cardmarket_listings': 'Cardmarket Listings',
    'dashboard.price_alerts': 'Price Spike Alerts',
    'dashboard.value_history': 'Collection Value (EUR) — 90 days',
    'collection.title': 'Collection',
    'collection.search': 'Search cards...',
    'collection.empty': 'Collection is empty. Sync your decks to populate it.',
    'collection.no_results': 'No cards found.',
    'settings.title': 'Settings & Sync',
    'settings.backup': 'Backup & Restore',
    'settings.download_backup': 'Download Backup',
    'settings.restore_backup': 'Restore from Backup',
    'wishlist.title': 'Wishlist',
    'wishlist.add': 'Add',
    'wishlist.empty': 'Wishlist is empty. Add cards you want to buy.',
    'wishlist.deal': 'Deal!',
    'wishlist.above_target': 'Above target',
    'wishlist.no_data': 'No data',
    'common.loading': 'Loading...',
    'common.page_of': 'Page {page} of {total}',
  },
  de: {
    'nav.dashboard': 'Übersicht',
    'nav.decks': 'Decks',
    'nav.collection': 'Sammlung',
    'nav.duplicates': 'Duplikate',
    'nav.cardmarket': 'Cardmarket',
    'nav.wishlist': 'Wunschliste',
    'nav.settings': 'Einstellungen',
    'dashboard.title': 'Übersicht',
    'dashboard.total_cards': 'Karten gesamt',
    'dashboard.unique_cards': 'Einzigartige Karten',
    'dashboard.value_eur': 'Sammlungswert (EUR)',
    'dashboard.value_usd': 'Sammlungswert (USD)',
    'dashboard.decks': 'Decks',
    'dashboard.cardmarket_listings': 'Cardmarket-Angebote',
    'dashboard.price_alerts': 'Preis-Spike-Alarme',
    'dashboard.value_history': 'Sammlungswert (EUR) — 90 Tage',
    'collection.title': 'Sammlung',
    'collection.search': 'Karten suchen...',
    'collection.empty': 'Sammlung ist leer. Synchronisiere deine Decks.',
    'collection.no_results': 'Keine Karten gefunden.',
    'settings.title': 'Einstellungen & Sync',
    'settings.backup': 'Sichern & Wiederherstellen',
    'settings.download_backup': 'Backup herunterladen',
    'settings.restore_backup': 'Aus Backup wiederherstellen',
    'wishlist.title': 'Wunschliste',
    'wishlist.add': 'Hinzufügen',
    'wishlist.empty': 'Wunschliste ist leer. Füge Karten hinzu, die du kaufen möchtest.',
    'wishlist.deal': 'Deal!',
    'wishlist.above_target': 'Über Zielpreis',
    'wishlist.no_data': 'Keine Daten',
    'common.loading': 'Laden...',
    'common.page_of': 'Seite {page} von {total}',
  },
};

function detectLanguage(): string {
  // Check HA language attribute
  const ha = document.documentElement.lang || document.body.getAttribute('data-lang');
  if (ha && ha.startsWith('de')) return 'de';
  // Browser language
  const nav = navigator.language;
  if (nav.startsWith('de')) return 'de';
  return 'en';
}

const currentLang = detectLanguage();

export function t(key: string, params?: Record<string, string | number>): string {
  const dict = translations[currentLang] || translations['en'];
  let value = dict[key] || translations['en'][key] || key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      value = value.replace(`{${k}}`, String(v));
    }
  }
  return value;
}

export function getLang(): string {
  return currentLang;
}
