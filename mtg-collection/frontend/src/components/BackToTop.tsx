import { useEffect, useState, RefObject } from 'react';
import { Button } from '@fluentui/react-components';
import { ArrowUp24Regular } from '@fluentui/react-icons';

interface Props {
  /** The scrollable container to watch and scroll to top. */
  scrollRef: RefObject<HTMLElement>;
  /** Scroll distance (px) before the button appears. */
  threshold?: number;
}

/** Floating "back to top" button shown after scrolling the given container. */
export default function BackToTop({ scrollRef, threshold = 400 }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => setVisible(el.scrollTop > threshold);
    onScroll();
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, [scrollRef, threshold]);

  if (!visible) return null;

  return (
    <Button
      appearance="primary"
      shape="circular"
      icon={<ArrowUp24Regular />}
      aria-label="Back to top"
      title="Back to top"
      onClick={() => scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
      style={{
        position: 'fixed',
        right: '24px',
        bottom: '24px',
        zIndex: 9999,
        boxShadow: '0 6px 20px rgba(0,0,0,0.45)',
      }}
    />
  );
}
