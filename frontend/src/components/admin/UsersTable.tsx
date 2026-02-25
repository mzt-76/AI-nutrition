
import React, { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { useToast } from '@/components/ui/use-toast';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Check, X, Copy, Loader2, Search } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  is_admin: boolean;
}

export const UsersTable = () => {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [filteredUsers, setFilteredUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Partial<UserProfile>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const { toast } = useToast();

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const { data, error } = await supabase
        .from('user_profiles')
        .select('id, email, full_name, is_admin');

      if (error) throw error;
      setUsers(data || []);
      setFilteredUsers(data || []);
    } catch (error) {
      console.error('Error fetching users:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch users',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  // Filter users based on search query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredUsers(users);
      return;
    }

    const query = searchQuery.toLowerCase().trim();
    const filtered = users.filter(
      (user) =>
        user.id.toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query) ||
        (user.full_name && user.full_name.toLowerCase().includes(query))
    );
    setFilteredUsers(filtered);
  }, [searchQuery, users]);

  const startEditing = (user: UserProfile) => {
    setEditingUser(user.id);
    setEditValues({
      email: user.email,
      full_name: user.full_name,
      is_admin: user.is_admin,
    });
  };

  const cancelEditing = () => {
    setEditingUser(null);
    setEditValues({});
  };

  const handleInputChange = (field: string, value: string | boolean) => {
    setEditValues((prev) => ({ ...prev, [field]: value }));
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: 'Copied',
      description: 'ID copied to clipboard',
    });
  };

  const saveChanges = async (userId: string) => {
    try {
      setSavingId(userId);
      const { error } = await supabase
        .from('user_profiles')
        .update({
          email: editValues.email,
          full_name: editValues.full_name,
          is_admin: editValues.is_admin,
        })
        .eq('id', userId);

      if (error) throw error;

      setUsers((prev) =>
        prev.map((user) =>
          user.id === userId
            ? {
                ...user,
                email: editValues.email || user.email,
                full_name: editValues.full_name === undefined ? user.full_name : editValues.full_name,
                is_admin: editValues.is_admin === undefined ? user.is_admin : editValues.is_admin,
              }
            : user
        )
      );

      // Update filtered users as well
      setFilteredUsers((prev) =>
        prev.map((user) =>
          user.id === userId
            ? {
                ...user,
                email: editValues.email || user.email,
                full_name: editValues.full_name === undefined ? user.full_name : editValues.full_name,
                is_admin: editValues.is_admin === undefined ? user.is_admin : editValues.is_admin,
              }
            : user
        )
      );

      toast({
        title: 'Success',
        description: 'User updated successfully',
      });

      cancelEditing();
    } catch (error) {
      console.error('Error updating user:', error);
      toast({
        title: 'Error',
        description: 'Failed to update user',
        variant: 'destructive',
      });
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-2xl font-semibold mb-4">User Management</h2>
      
      <div className="mb-4 relative">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
          <Input
            placeholder="Search by ID, email or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 w-full"
          />
        </div>
      </div>
      
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead width="20%">ID</TableHead>
              <TableHead width="30%">Email</TableHead>
              <TableHead width="20%">Name</TableHead>
              <TableHead width="10%">Admin</TableHead>
              <TableHead width="20%">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array(3).fill(0).map((_, index) => (
                <TableRow key={`loading-${index}`}>
                  <TableCell width="20%"><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell width="30%"><Skeleton className="h-4 w-40" /></TableCell>
                  <TableCell width="20%"><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell width="10%"><Skeleton className="h-4 w-10" /></TableCell>
                  <TableCell width="20%"><Skeleton className="h-8 w-16" /></TableCell>
                </TableRow>
              ))
            ) : filteredUsers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-4">
                  {searchQuery ? 'No users found matching your search' : 'No users found'}
                </TableCell>
              </TableRow>
            ) : (
              filteredUsers.map((user) => (
                <TableRow key={user.id}>
                  <TableCell width="20%">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs truncate max-w-[150px]">{user.id}</span>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={() => copyToClipboard(user.id)}
                        className="h-6 w-6 flex-shrink-0"
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell width="30%">
                    {editingUser === user.id ? (
                      <Input
                        value={editValues.email}
                        onChange={(e) => handleInputChange('email', e.target.value)}
                        className="w-full"
                      />
                    ) : (
                      <div className="truncate max-w-[200px]">{user.email}</div>
                    )}
                  </TableCell>
                  <TableCell width="20%">
                    {editingUser === user.id ? (
                      <Input
                        value={editValues.full_name || ''}
                        onChange={(e) => handleInputChange('full_name', e.target.value)}
                        className="w-full"
                      />
                    ) : (
                      <div className="truncate max-w-[150px]">{user.full_name || '-'}</div>
                    )}
                  </TableCell>
                  <TableCell width="10%">
                    {editingUser === user.id ? (
                      <Switch
                        checked={!!editValues.is_admin}
                        onCheckedChange={(value) => handleInputChange('is_admin', value)}
                      />
                    ) : (
                      <span>{user.is_admin ? 'Yes' : 'No'}</span>
                    )}
                  </TableCell>
                  <TableCell width="20%">
                    {editingUser === user.id ? (
                      <div className="flex space-x-2">
                        <Button
                          size="sm"
                          onClick={() => saveChanges(user.id)}
                          className="bg-green-500 hover:bg-green-600"
                          disabled={savingId === user.id}
                        >
                          {savingId === user.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Check className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={cancelEditing}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startEditing(user)}
                      >
                        Edit
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
