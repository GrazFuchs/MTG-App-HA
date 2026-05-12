import { MessageBar, MessageBarBody, MessageBarTitle } from '@fluentui/react-components';
import type { ReactNode } from 'react';

interface Props {
  title: string;
  message: string;
  action?: ReactNode;
}

export function ErrorBanner({ title, message, action }: Props) {
  return (
    <MessageBar intent="error">
      <MessageBarBody>
        <MessageBarTitle>{title}</MessageBarTitle>
        {message}
        {action && <div style={{ marginTop: 8 }}>{action}</div>}
      </MessageBarBody>
    </MessageBar>
  );
}
