import { Suspense } from "react"
import { AuthForm } from "@/components/auth/AuthForm"

export default function LoginPage() {
  // useSearchParams (for the ?next= destination) needs a Suspense boundary.
  return (
    <Suspense fallback={null}>
      <AuthForm mode="login" />
    </Suspense>
  )
}
