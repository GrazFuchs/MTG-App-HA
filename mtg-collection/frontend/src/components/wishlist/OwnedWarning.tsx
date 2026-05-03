import { MessageBar, MessageBarBody } from '@fluentui/react-components';

interface Props {
  cardName: string | null;
  ownedQuantity: number;
}

export default function OwnedWarning({ cardName, ownedQuantity }: Props) {
  if (!cardName || ownedQuantity <= 0) return null;
  return (
    <MessageBar intent="warning" style={{ marginTop: '8px' }}>
      <MessageBarBody>
        You already own {ownedQuantity} {ownedQuantity === 1 ? 'copy' : 'copies'} of {cardName}. Add anyway?
      </MessageBarBody>
    </MessageBar>
  );
}
