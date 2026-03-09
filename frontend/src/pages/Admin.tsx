
import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { UsersTable } from '@/components/admin/UsersTable';
import { ConversationsTable } from '@/components/admin/ConversationsTable';
import { useAdmin } from '@/hooks/useAdmin';
import { Button } from '@/components/ui/button';
import { MessageSquare } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export const Admin = () => {
  const { isAdmin, loading } = useAdmin();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('users');

  useEffect(() => {
    if (!loading && !isAdmin) {
      navigate('/');
    }
  }, [isAdmin, loading, navigate]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center gradient-bg">
        <div className="animate-pulse">Chargement...</div>
      </div>
    );
  }

  if (!isAdmin) {
    return null;
  }

  return (
    <div className="flex flex-col min-h-screen gradient-bg">
      <div className="border-b border-border/50">
        <div className="flex items-center justify-between px-4 py-2">
          <h1 className="text-lg font-semibold">Tableau de bord admin</h1>
          <Button variant="outline" size="sm" asChild>
            <Link to="/">
              <MessageSquare className="mr-2 h-4 w-4" />
              Retour au chat
            </Link>
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <div className="flex justify-center mb-6">
          <Tabs
            defaultValue="users"
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full max-w-[95%] lg:max-w-[1200px]"
          >
            <div className="flex justify-center mb-6">
              <TabsList className="grid w-full max-w-[400px] grid-cols-2">
                <TabsTrigger
                  value="users"
                  className="transition-all data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
                >
                  Utilisateurs
                </TabsTrigger>
                <TabsTrigger
                  value="conversations"
                  className="transition-all data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
                >
                  Conversations
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="users" className="mt-0">
              <UsersTable />
            </TabsContent>

            <TabsContent value="conversations" className="mt-0">
              <div className="p-4">
                <h2 className="text-2xl font-semibold mb-4">Gestion des conversations</h2>
                <ConversationsTable />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default Admin;
