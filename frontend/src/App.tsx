import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { AppLayout } from './components/Layout'
import { Skeleton } from './components/ui'
import { AccountPage } from './features/account/AccountPage'
import { AskPage } from './features/ask/AskPage'
import {
  ForgotPasswordPage,
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
  VerifyEmailPage,
} from './features/auth/AuthPages'
import { HomePage } from './features/home/HomePage'
import { InterviewPage } from './features/interview/InterviewPage'
import { CookTodayPage } from './features/kitchen/CookTodayPage'
import { OnboardingPage } from './features/onboarding/OnboardingPage'
import { NewPlanPage } from './features/plans/NewPlanPage'
import { NutritionistHomePage, NutritionistPlanPage } from './features/plans/NutritionistPages'
import { PlanHomePage, PlanPage } from './features/plans/PlanPages'
import { ProfilePage } from './features/profile/ProfilePage'
import { BookPage, BooksPage } from './features/recipes/BooksPages'
import { ImportJobPage, ImportPage } from './features/recipes/ImportPages'
import { PublicProfilePage } from './features/recipes/Community'
import { RecipeDetailPage } from './features/recipes/RecipeDetailPage'
import { RecipeFormPage } from './features/recipes/RecipeFormPage'
import { RecipesPage } from './features/recipes/RecipesPage'
import { SharedRecipePage } from './features/recipes/Sharing'
import { ShoppingHomePage, ShoppingPage } from './features/shopping/ShoppingPages'
import { useProfile } from './api/hooks'
import { useAuth } from './lib/auth'

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <Skeleton className="m-6 h-24" />
  if (!user) {
    // Dopo il login si torna dove si voleva andare: un link aperto da
    // sloggato non deve finire sulla home.
    const next = location.pathname === '/' ? '' : `?next=${encodeURIComponent(location.pathname)}`
    return <Navigate to={`/accedi${next}`} replace />
  }
  return children
}

/** Finche' il profilo non e' completo l'app apre il wizard al posto della home. */
function RequireOnboarding({ children }: { children: JSX.Element }) {
  const { data: profile, isPending, isError } = useProfile()
  if (isPending) return <Skeleton className="m-6 h-24" />
  // Se il profilo non si carica non si blocca l'app: le pagine mostrano l'errore.
  if (!isError && !profile.onboarding_completed) return <Navigate to="/benvenuto" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/accedi" element={<LoginPage />} />
      <Route path="/registrati" element={<RegisterPage />} />
      <Route path="/verifica-email/:token" element={<VerifyEmailPage />} />
      <Route path="/password-dimenticata" element={<ForgotPasswordPage />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />
      {/* Ricetta condivisa (ADR 0012): si apre anche senza account. */}
      <Route path="/r/:token" element={<SharedRecipePage />} />
      <Route path="/u/:handle" element={<PublicProfilePage />} />
      <Route
        path="/benvenuto"
        element={
          <RequireAuth>
            <OnboardingPage />
          </RequireAuth>
        }
      />
      <Route
        path="/intervista"
        element={
          <RequireAuth>
            <InterviewPage />
          </RequireAuth>
        }
      />
      {/* Chat su profilo e piano (ADR 0016): a tutto schermo come l'intervista. */}
      <Route
        path="/chiedi"
        element={
          <RequireAuth>
            <RequireOnboarding>
              <AskPage />
            </RequireOnboarding>
          </RequireAuth>
        }
      />
      <Route
        element={
          <RequireAuth>
            <RequireOnboarding>
              <AppLayout />
            </RequireOnboarding>
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="cosa-cucino" element={<CookTodayPage />} />
        <Route path="piano" element={<PlanHomePage />} />
        <Route path="piano/nuovo" element={<NewPlanPage />} />
        <Route path="piano/nutrizionista" element={<NutritionistHomePage />} />
        <Route path="piano/nutrizionista/:planId" element={<NutritionistPlanPage />} />
        <Route path="piano/:planId" element={<PlanPage />} />
        <Route path="spesa" element={<ShoppingHomePage />} />
        <Route path="spesa/:listId" element={<ShoppingPage />} />
        <Route path="ricette" element={<RecipesPage />} />
        <Route path="ricette/nuova" element={<RecipeFormPage />} />
        <Route path="ricette/ricettari" element={<BooksPage />} />
        <Route path="ricette/ricettari/:bookId" element={<BookPage />} />
        <Route path="ricette/importa" element={<ImportPage />} />
        <Route path="ricette/importa/:jobId" element={<ImportJobPage />} />
        <Route path="ricette/:recipeId" element={<RecipeDetailPage />} />
        <Route path="ricette/:recipeId/modifica" element={<RecipeFormPage />} />
        <Route path="profilo" element={<ProfilePage />} />
        <Route path="profilo/account" element={<AccountPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
