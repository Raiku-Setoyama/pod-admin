import { Suspense } from "react";
import { LoginForm } from "@/features/auth/components/login-form";
import { PageLoading } from "@/components/common/loading-spinner";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Suspense fallback={<PageLoading />}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
