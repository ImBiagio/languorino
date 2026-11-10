# 0001 — Stack e fondamenta da languorino

Il progetto parte da [languorino](https://github.com/ImBiagio/languorino), le
fondamenta comuni estratte da soldino e regalino (e cinemino per mail e
deploy): Django + DRF + Postgres + Celery/Redis, React/Vite/TypeScript con
Tailwind e token Material 3, auth JWT con refresh in cookie `httpOnly`, mail
via Celery e SMTP Brevo, gettext italiano/inglese, deploy con GitHub Action →
ghcr.io → Watchtower dietro il proxy edge condiviso.

**Lingue.** Italiano lingua sorgente dei msgid, inglese in
`backend/locale/en/LC_MESSAGES`. Il frontend usa lo stesso catalogo gettext di
Django: le sue stringhe stanno nel dominio `djangojs` (estratte dal JS
traspilato in `frontend/.i18n/`) e arrivano come JSON da `/api/i18n/catalog`.
La lingua scelta vive nel cookie standard di Django e, da loggati, su
`User.language`, così anche le mail partono nella lingua giusta. Il nome
dell'app sta in `settings.APP_NAME`, fuori dalle stringhe tradotte.

**Perché:** le fondamenta sono già provate in produzione sullo stesso server;
una base diversa vorrebbe dire più modi di fare auth, mail e deploy da
mantenere.

**Costo accettato:** Celery, Redis e beat girano anche quando servono solo per
mail e pulizia dei token: tre container in più per un'app piccola. I fix alle
parti comuni vanno portati a mano fra i progetti e in languorino (sono copie,
non una libreria).

**Quando rivederla:** se le parti comuni divergono spesso, estrarle in un
pacchetto condiviso.
