import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  makeStyles,
  tokens,
  Title2,
  Body1,
  Caption1,
  Spinner,
  Button,
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Badge,
} from '@fluentui/react-components';
import { Delete24Regular } from '@fluentui/react-icons';
import { api, WishlistItem } from '../api';
import WishlistAddForm from '../components/wishlist/WishlistAddForm';

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '12px',
    marginTop: '12px',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
  },
  tableWrap: { marginTop: '16px', overflowX: 'auto' },
  deal: {
    backgroundColor: tokens.colorPaletteGreenBackground1,
  },
});

export default function Wishlist() {
  const styles = useStyles();
  const queryClient = useQueryClient();

  const { data: items = [], isLoading } = useQuery<WishlistItem[]>({
    queryKey: ['wishlist'],
    queryFn: () => api.getWishlist(),
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => api.removeFromWishlist(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['wishlist'] }),
  });

  const deals = items.filter(i => i.is_deal);

  if (isLoading) return <Spinner label="Loading wishlist..." />;

  return (
    <div>
      <Title2>Wishlist ({items.length} cards{deals.length > 0 ? `, ${deals.length} deals!` : ''})</Title2>

      <WishlistAddForm onAdded={() => queryClient.invalidateQueries({ queryKey: ['wishlist'] })} />

      {items.length === 0 ? (
        <Body1 style={{ marginTop: 24 }}>Wishlist is empty. Add cards you want to buy.</Body1>
      ) : (
        <div className={styles.tableWrap}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Card</TableHeaderCell>
                <TableHeaderCell>Set</TableHeaderCell>
                <TableHeaderCell>Priority</TableHeaderCell>
                <TableHeaderCell>Target Price</TableHeaderCell>
                <TableHeaderCell>Current Price</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell>Notes</TableHeaderCell>
                <TableHeaderCell />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map(item => (
                <TableRow key={item.id} className={item.is_deal ? styles.deal : undefined}>
                  <TableCell>
                    {item.card_name}
                    {item.is_foil && <Badge appearance="outline" size="small" style={{ marginLeft: 4 }}>Foil</Badge>}
                    {item.quantity > 1 && <Caption1> ×{item.quantity}</Caption1>}
                  </TableCell>
                  <TableCell>
                    <Caption1>{item.set_code ? item.set_code.toUpperCase() : '—'}</Caption1>
                  </TableCell>
                  <TableCell>{'★'.repeat(item.priority)}{'☆'.repeat(5 - item.priority)}</TableCell>
                  <TableCell>
                    {item.target_price_eur > 0 ? `€${item.target_price_eur.toFixed(2)}` : '—'}
                  </TableCell>
                  <TableCell>
                    {item.current_price_eur != null ? `€${item.current_price_eur.toFixed(2)}` : '—'}
                  </TableCell>
                  <TableCell>
                    {item.is_deal ? (
                      <Badge appearance="filled" color="success">Deal!</Badge>
                    ) : item.current_price_eur != null && item.target_price_eur > 0 ? (
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
