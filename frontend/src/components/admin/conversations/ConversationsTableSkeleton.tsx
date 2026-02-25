
import React from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';

export const ConversationsTableSkeleton = () => {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={i}>
          <TableCell width="20%">
            <Skeleton className="h-4 w-full" />
          </TableCell>
          <TableCell width="30%">
            <Skeleton className="h-4 w-full" />
          </TableCell>
          <TableCell width="25%">
            <Skeleton className="h-4 w-full" />
          </TableCell>
          <TableCell width="25%">
            <Skeleton className="h-4 w-full" />
          </TableCell>
        </TableRow>
      ))}
    </>
  );
};
