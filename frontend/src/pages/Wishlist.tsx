import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  makeStyles,
  tokens,
  Title2,
  Body1,
  Caption1,
  Spinner,
  Input,
  Button,
  Card,
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Badge,
} from '@fluentui/react-components';
import { Add24Regular, Delete24Regular } from '@fluentui/react-icons';
import { api, WishlistItem } from '../api';

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '12px',
    marginTop: '12px',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
  },
  input: { minWidth: '200px' },
  tableWrap: { marginTop: '16px', overflowX: 'auto' },
  deal: {
    backgroundColor: tokens.colorPaletteGreenBackground1,
  },
});

export default function Wishlist() {
  const styles = useStyles();
  const queryClient = useQueryClient();
  const [cardName, setCardName] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [notes, setNotes] = useState('');

  const { data: items = [], isLoading } = useQuery<WishlistItem[]>({
    queryKey: ['wishlist'],
    queryFn: () => api.getWishlist(),
  });

  const addMutation = useMutation({
    mutationFn: (data: { card_name: string; max_price_eur?: number; notes?: string }) =>
      api.addToWishlist(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist'] });
      setCardName('');
      setMaxPrice('');
      setNotes('');
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => api.removeFromWishlist(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['wishlist'] }),
  });

  const handleAdd = () => {
    if (!cardName.trim()) return;
    addMutation.mutate({
      card_name: cardName.trim(),
      max_price_eur: maxPrice ? parseFloat(maxPrice) : 0,
      notes: notes.trim(),
    });
  };

  const deals = items.filter(i => i.is_deal);

  if (isLoading) return <Spinner label="Loading wishlist..." />;

  return (
    <div>
      <Title2>Wishlist ({items.length} cards{deals.length > 0 ? `, ${deals.length} deals!` : ''})</Title2>

      <div className={styles.controls}>
        <Input
          placeholder="Card name"
          value={cardName}
          onChange={(_, d) => setCardName(d.value)}
          className={styles.input}
        />
        <Input
          placeholder="Max price (EUR)"
          type="number"
          value={maxPrice}
          onChange={(_, d) => setMaxPrice(d.value)}
          style={{ width: 130 }}
        />
        <Input
          placeholder="Notes"
          value={notes}
          onChange={(_, d) => setNotes(d.value)}
          style={{ width: 200 }}
        />
        <Button
          icon={<Add24Regular />}
          appearance="primary"
          onClick={handleAdd}
          disabled={addMutation.isPending || !cardName.trim()}
        >
          Add
        </Button>
      </div>

      {addMutation.isError && (
        <Body1 style={{ color: tokens.colorPaletteRedForeground1, marginTop: 8 }}>
          {(addMutation.error as Error).message}
        </Body1>
      )}

      {items.length === 0 ? (
        <Body1 style={{ marginTop: 24 }}>Wishlist is empty. Add cards you want to buy.</Body1>
      ) : (
        <div className={styles.tableWrap}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Card</TableHeaderCell>
                <TableHeaderCell>Max Price</TableHeaderCell>
                <TableHeaderCell>Current Price</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell>Notes</TableHeaderCell>
                <TableHeaderCell />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map(item => (
                <TableRow key={item.id} className={item.is_deal ? styles.deal : undefined}>
                  <TableCell>{item.card_name}</TableCell>
                  <TableCell>
                    {item.max_price_eur > 0 ? `€${item.max_price_eur.toFixed(2)}` : '—'}
                  </TableCell>
                  <TableCell>
                    {item.current_price != null ? `€${item.current_price.toFixed(2)}` : '—'}
                  </TableCell>
                  <TableCell>
                    {item.is_deal ? (
                      <Badge appearance="filled" color="success">Deal!</Badge>
                    ) : item.current_price != null && item.max_price_eur > 0 ? (
                      <Caption1>Above target</Caption1>
                    ) : (
                      <Caption1>No data</Caption1>
                    )}
                  </TableCell>
                  <TableCell><Caption1>{item.notes}</Caption1></TableCell>
                  <TableCell>
                    <Button
                      icon={<Delete24Regular />}
                      appearance="subtle"
                      size="small"
                      onClick={() => removeMutation.mutate(item.id)}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
