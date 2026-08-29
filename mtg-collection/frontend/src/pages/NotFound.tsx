import { useNavigate } from 'react-router-dom';
import { Button } from '@fluentui/react-components';
import { sothera } from '../theme/sothera';

import { t } from '../i18n';
/**
 * Shown for any path the router does not know.
 *
 * Without it an unknown path rendered an empty content area — indistinguishable
 * from a page whose data happens to be empty, which is the same "silence reads
 * as a result" failure the error banners exist to prevent.
 */
export function NotFound() {
  const navigate = useNavigate();
  return (
    <div style={{ padding: '48px 0', textAlign: 'center' }}>
      <div style={{
        fontFamily: sothera.fontMono, fontSize: 11, letterSpacing: 2,
        color: sothera.fgFaint, textTransform: 'uppercase', marginBottom: 10,
      }}>
        404
      </div>
      <div style={{ fontFamily: sothera.fontDisplay, fontSize: 22, color: sothera.fg, marginBottom: 6 }}>
        {t('notfound.title')}
      </div>
      <div style={{ fontSize: 13, color: sothera.fgMuted, marginBottom: 18 }}>
        <code>{window.location.pathname}</code> {t('notfound.body')}
      </div>
      <Button appearance="primary" onClick={() => navigate('/')}>
        {t('notfound.back')}
      </Button>
    </div>
  );
}
