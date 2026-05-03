import { makeStyles, tokens } from '@fluentui/react-components';
import { Star24Filled, Star24Regular } from '@fluentui/react-icons';

const useStyles = makeStyles({
  wrapper: { display: 'flex', gap: '2px', alignItems: 'center' },
  star: { cursor: 'pointer', color: tokens.colorPaletteYellowForeground1 },
  starEmpty: { cursor: 'pointer', color: tokens.colorNeutralForeground4 },
});

interface Props {
  value: number;
  onChange: (v: number) => void;
}

const labels = ['', 'Low', 'Below average', 'Normal', 'High', 'Must-have'];

export default function PrioritySelector({ value, onChange }: Props) {
  const styles = useStyles();
  return (
    <div className={styles.wrapper} role="group" aria-label="Priority">
      {[1, 2, 3, 4, 5].map(n => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          className={n <= value ? styles.star : styles.starEmpty}
          aria-label={`Priority ${n}: ${labels[n]}`}
          title={labels[n]}
          style={{ background: 'none', border: 'none', padding: '2px' }}
        >
          {n <= value ? <Star24Filled /> : <Star24Regular />}
        </button>
      ))}
    </div>
  );
}
