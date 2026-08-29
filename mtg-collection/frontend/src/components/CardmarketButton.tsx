import { Button, Tooltip } from '@fluentui/react-components';
import { Open16Regular } from '@fluentui/react-icons';

import { t } from '../i18n';
/** Build a Cardmarket product-search URL for a card name. */
export function cardmarketSearchUrl(name: string): string {
  return `https://www.cardmarket.com/en/Magic/Products/Search?searchString=${encodeURIComponent(name)}`;
}

interface Props {
  cardName: string;
  size?: 'small' | 'medium';
}

/** Small icon button that opens the card's Cardmarket page in a new tab. */
export function CardmarketButton({ cardName, size = 'small' }: Props) {
  return (
    <Tooltip content={t('common.open_cardmarket')} relationship="label">
      <Button
        appearance="subtle"
        size={size}
        icon={<Open16Regular />}
        aria-label={`Open ${cardName} on Cardmarket`}
        onClick={(e) => {
          e.stopPropagation();
          window.open(cardmarketSearchUrl(cardName), '_blank', 'noopener,noreferrer');
        }}
      />
    </Tooltip>
  );
}
