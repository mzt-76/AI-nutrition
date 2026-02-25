
import { AuthForm } from '@/components/auth/AuthForm';
import { Salad } from 'lucide-react';

const Login = () => {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gradient-bg">
      <div className="mb-8 text-center">
        <div className="flex justify-center mb-4">
          <div className="h-14 w-14 rounded-full gradient-green flex items-center justify-center glow-green">
            <Salad className="h-7 w-7 text-white" />
          </div>
        </div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Nutritionniste IA</h1>
        <p className="text-muted-foreground">Connectez-vous pour commencer</p>
      </div>
      <AuthForm />
    </div>
  );
};

export default Login;
