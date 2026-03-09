
import React from 'react';
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { ConversationRow } from './conversations/ConversationRow';
import { ConversationsTableSkeleton } from './conversations/ConversationsTableSkeleton';
import { ConversationDialog } from './conversations/ConversationDialog';
import { SearchBar } from './conversations/SearchBar';
import { useConversations } from './conversations/useConversations';
import { Calendar } from 'lucide-react';

export const ConversationsTable = () => {
  const {
    filteredConversations,
    loading,
    selectedConversation,
    openDialog,
    loadingMessages,
    searchQuery,
    setSearchQuery,
    copyToClipboard,
    viewConversation,
    handleDialogChange,
    sortOrder,
    toggleSortOrder,
  } = useConversations();

  return (
    <div>
      <SearchBar searchQuery={searchQuery} setSearchQuery={setSearchQuery} />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead width="20%" className="cursor-pointer" onClick={toggleSortOrder}>
                <div className="flex items-center space-x-1">
                  <Calendar className="h-4 w-4" />
                  <span>Created At</span>
                  <span className="ml-1">{sortOrder === 'desc' ? '↓' : '↑'}</span>
                </div>
              </TableHead>
              <TableHead width="30%">Title</TableHead>
              <TableHead width="25%">User ID</TableHead>
              <TableHead width="25%">Session ID</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <ConversationsTableSkeleton />
            ) : filteredConversations.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center py-4">
                  {searchQuery ? 'No conversations found matching your search' : 'No conversations found'}
                </TableCell>
              </TableRow>
            ) : (
              filteredConversations.map((conversation) => (
                <ConversationRow
                  key={conversation.session_id}
                  conversation={conversation}
                  viewConversation={viewConversation}
                  copyToClipboard={copyToClipboard}
                />
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <ConversationDialog
        open={openDialog}
        onOpenChange={handleDialogChange}
        selectedConversation={selectedConversation}
        loadingMessages={loadingMessages}
      />
    </div>
  );
};
