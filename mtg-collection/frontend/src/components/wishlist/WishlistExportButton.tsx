import { useState } from 'react';
import {
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  SplitButton,
  makeStyles,
  tokens,
  Toast,
  Toaster,
  useToastController,
  useId,
} from '@fluentui/react-components';
import { ArrowDownload24Regular, Copy24Regular, Open24Regular } from '@fluentui/react-icons';
import { t } from '../../i18n';

const useStyles = makeStyles({
  wrapper: { display: 'inline-flex' },
});

function getBaseUrl(): string {
  const path = window.location.pathname;
  const match = path.match(/^(\/api\/hassio_ingress\/[^/]+)/);
  return match ? match[1] : '';
}

export default function WishlistExportButton() {
  const styles = useStyles();
  const toasterId = useId('export-toaster');
  const { dispatchToast } = useToastController(toasterId);
  const [loading, setLoading] = useState(false);

  const downloadFile = (content: string, filename: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCardmarketExport = async () => {
    setLoading(true);
    try {
      const base = getBaseUrl();
      const res = await fetch(`${base}/api/wishlist/export/cardmarket`);
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const text = await res.text();
      downloadFile(text, 'wishlist-cardmarket.txt', 'text/plain');
    } catch (e: any) {
      dispatchToast(
        <Toast>{e.message || 'Export failed'}</Toast>,
        { intent: 'error' }
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCopyCardmarket = async () => {
    try {
      const base = getBaseUrl();
      const res = await fetch(`${base}/api/wishlist/export/cardmarket`);
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const text = await res.text();
      await navigator.clipboard.writeText(text);
      dispatchToast(
        <Toast>{t('wishlist.export_copied')}</Toast>,
        { intent: 'success' }
      );
    } catch (e: any) {
      dispatchToast(
        <Toast>{e.message || 'Copy failed'}</Toast>,
        { intent: 'error' }
      );
    }
  };

  const handleJsonExport = async () => {
    setLoading(true);
    try {
      const base = getBaseUrl();
      const res = await fetch(`${base}/api/wishlist/export/json`);
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const text = await res.text();
      downloadFile(text, 'wishlist.json', 'application/json');
    } catch (e: any) {
      dispatchToast(
        <Toast>{e.message || 'Export failed'}</Toast>,
        { intent: 'error' }
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Toaster toasterId={toasterId} />
      <div className={styles.wrapper}>
        <Menu>
          <MenuTrigger disableButtonEnhancement>
            <SplitButton
              icon={<ArrowDownload24Regular />}
              appearance="subtle"
              primaryActionButton={{ onClick: handleCardmarketExport, disabled: loading }}
            >
              {t('wishlist.export_cardmarket')}
            </SplitButton>
          </MenuTrigger>
          <MenuPopover>
            <MenuList>
              <MenuItem icon={<ArrowDownload24Regular />} onClick={handleCardmarketExport}>
                {t('wishlist.export_cardmarket_download')}
              </MenuItem>
              <MenuItem icon={<Copy24Regular />} onClick={handleCopyCardmarket}>
                {t('wishlist.export_copy_clipboard')}
              </MenuItem>
              <MenuItem icon={<Open24Regular />} onClick={() => window.open('https://www.cardmarket.com/en/Magic/Wants/Add', '_blank')}>
                {t('wishlist.export_open_cardmarket')}
              </MenuItem>
              <MenuItem icon={<ArrowDownload24Regular />} onClick={handleJsonExport}>
                {t('wishlist.export_json')}
              </MenuItem>
            </MenuList>
          </MenuPopover>
        </Menu>
      </div>
    </>
  );
}
