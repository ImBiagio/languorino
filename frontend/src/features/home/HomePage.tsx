import { Page, PageHeader } from '../../components/Layout'
import { EmptyState } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { gettext, interpolate } from '../../lib/i18n'

/** Pagina iniziale del template: da sostituire con la prima sezione vera dell'app. */
export function HomePage() {
  const { user } = useAuth()
  return (
    <Page>
      <PageHeader
        title={interpolate(gettext('Ciao %s'), [user?.display_name ?? ''])}
        subtitle={gettext('Da qui parte la tua app.')}
      />
      <div className="px-5 md:px-8">
        <EmptyState
          icon="rocket_launch"
          title={gettext('Ancora niente qui')}
          description={gettext(
            'Aggiungi le sezioni in components/Layout.tsx e le rotte in App.tsx.',
          )}
        />
      </div>
    </Page>
  )
}
