# 0005 — Gemini dietro l'app `ai`, lavori lunghi nell'app `jobs`

Ogni chiamata all'LLM passa da `apps/ai/client.py` (`generate`): Gemini con
l'SDK `google-genai`, API `v1beta` esplicita, risposta JSON vincolata a un
modello pydantic, un modello principale (`GEMINI_MODEL`, default
`gemini-flash-latest`) e delle riserve (`GEMINI_FALLBACK_MODELS`). Un modello
che risponde sovraccarico (429/5xx) resta "giù" in cache per qualche minuto;
chiave rifiutata e richieste non valide si fermano subito. Ogni chiamata si
registra in `AiCall` (funzione, modello, token, durata, esito, utente).

Il lavoro lungo è un `Job` (`apps/jobs`): la richiesta salva i file
(`JobFile`, tipo riconosciuto dai primi byte, foto ridotte a 2400 px e senza
EXIF), crea il job e risponde subito con 202; il task `run_job` gira dopo il
commit sulla coda Celery `ai`, servita da un worker suo (`worker-ai`, due alla
volta). Il job finisce in `ready` con la bozza in `result`, o in `failed` con
un messaggio leggibile; si può riprovare. Le bozze diventano dati solo con
`POST /api/jobs/{id}/confirm`, che le valida con lo stesso serializer delle
ricette scritte a mano. Il primo lavoro è l'import di ricette da foto e PDF
(`recipes/importing.py`): i file vanno direttamente a Gemini, che legge
scrittura a mano, stampa e PDF senza OCR separato, e segna i campi dedotti.

**Perché:** è lo schema già in produzione su soldino per scontrini ed estratti
conto. Un solo punto d'accesso tiene in un posto prompt, schemi, retry e costi;
il job evita richieste HTTP appese per decine di secondi; la conferma esplicita
è il principio "l'LLM propone, l'utente conferma".

**Costo accettato:** un container in più (`worker-ai`). I file degli import
restano sul disco 30 giorni (`JOB_FILES_KEEP_DAYS`), poi li toglie il task
notturno `clean_jobs`. Un PDF va a Gemini intero: oltre ~18 MB va diviso a mano.
Il messaggio d'errore del worker è nella lingua dell'utente al momento
dell'avvio.

**Quando rivederla:** se gli import diventano tanti o i PDF lunghi, dividere
le pagine in più chiamate; se serve lo streaming (intervista a voce), la
conversazione non passerà da un job.
