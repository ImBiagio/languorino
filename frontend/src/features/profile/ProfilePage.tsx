import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useProfile, useUpdateProfile } from '../../api/hooks'
import { Page, PageHeader } from '../../components/Layout'
import { ErrorBanner, Icon, RowsSkeleton } from '../../components/ui'
import { ApiError } from '../../lib/api'
import { gettext } from '../../lib/i18n'
import type { Profile, ProfileDraft } from '../../lib/types'
import { SECTIONS, changesFor, draftFrom, isDirty } from './sections'
import type { SectionDef } from './sections'

/** Il profilo alimentare, sezione per sezione, piu' il link all'account. */
export function ProfilePage() {
  const { data: profile, error } = useProfile()
  return (
    <Page>
      <PageHeader
        title={gettext('Profilo')}
        subtitle={gettext('Quello che Languorino sa di te per proporti cosa mangiare.')}
      />
      <div className="grid gap-4 px-5 md:px-8">
        <ErrorBanner error={error} />
        {!profile && !error && <RowsSkeleton rows={4} />}
        <Link
          to="/intervista"
          className="state flex items-center gap-4 rounded-card bg-primary-container p-5 text-on-primary-container"
        >
          <Icon name="forum" size={24} />
          <span className="min-w-0 flex-1">
            <span className="block text-body-large font-medium">
              {gettext('Aggiorna il profilo chiacchierando')}
            </span>
            <span className="block text-body-small opacity-80">
              {gettext('Raccontami cosa è cambiato, anche a voce: poi controlli e salvi')}
            </span>
          </span>
          <Icon name="chevron_right" size={24} />
        </Link>
        {profile &&
          SECTIONS.map((section) => (
            <SectionCard key={section.id} section={section} profile={profile} />
          ))}
        <Link
          to="/profilo/account"
          className="state flex items-center gap-4 rounded-card bg-surface-container-low p-5"
        >
          <Icon name="manage_accounts" size={24} />
          <span className="min-w-0 flex-1">
            <span className="block text-body-large font-medium">{gettext('Account')}</span>
            <span className="block text-body-small text-on-surface-variant">
              {gettext('Email, password, lingua')}
            </span>
          </span>
          <Icon name="chevron_right" size={24} />
        </Link>
      </div>
    </Page>
  )
}

function SectionCard({ section, profile }: { section: SectionDef; profile: Profile }) {
  const update = useUpdateProfile()
  const [draft, setDraft] = useState<ProfileDraft>(() => draftFrom(profile))
  const [saved, setSaved] = useState(false)
  const dirty = section.fields.length > 0 && isDirty(draft, profile, section.fields)
  const errors = update.error instanceof ApiError ? update.error.fieldErrors() : {}

  return (
    <section className="rounded-card bg-surface-container-low p-5">
      <header className="mb-4 flex items-start gap-3">
        <Icon name={section.icon} size={24} className="mt-0.5 text-primary" />
        <div className="min-w-0 flex-1">
          <h2 className="text-body-large font-medium">{section.title}</h2>
          <p className="text-body-small text-on-surface-variant">{section.subtitle}</p>
        </div>
      </header>
      <section.Component
        draft={draft}
        set={(changes) => {
          setSaved(false)
          setDraft((current) => ({ ...current, ...changes }))
        }}
        errors={errors}
        profile={profile}
      />
      {section.fields.length > 0 && (
        <div className="mt-4 grid gap-3">
          <ErrorBanner error={update.error} />
          <div className="flex justify-end gap-2">
            {dirty && (
              <button
                type="button"
                className="btn-text"
                onClick={() => {
                  update.reset()
                  setDraft(draftFrom(profile))
                }}
              >
                {gettext('Annulla')}
              </button>
            )}
            <button
              type="button"
              className="btn-tonal"
              disabled={!dirty || update.isPending}
              onClick={async () => {
                try {
                  const next = await update.mutateAsync(changesFor(draft, section.fields))
                  // Il server ripulisce (spazi, ordine dei pasti): si riparte da li'.
                  setDraft(draftFrom(next))
                  setSaved(true)
                } catch {
                  // L'errore resta in update.error e si vede sopra.
                }
              }}
            >
              {saved && !dirty ? gettext('Salvato') : gettext('Salva')}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
