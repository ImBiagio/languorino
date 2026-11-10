# 0007 — Piano alimentare: codice per la sicurezza e il prep, LLM per la varietà

Il piano (`apps/plans`) copre 1–4 settimane e si genera una settimana alla
volta con un task sulla coda `ai` (`plan_week`), come i ricettari PDF: ogni
settimana è una chiamata che compone i pasti più una chiamata per ogni ricetta
nuova (al massimo 6 a settimana). Gemini sovraccarico: il task aspetta e
riprova; piano fermo da 15 minuti: lo riprende `resume_stalled_plans`.

Diviso così:

- **Calendario del prep (codice, `schedule.py`)**: per ogni pasto il giorno in
  cui si cucina, dalla modalità scelta (al momento, la sera prima per il
  pranzo, ogni 2 o 3 giorni, domenica e mercoledì). Si preparano in anticipo
  solo pranzo e cena. Da qui i "giorni di attesa" di ogni pasto.
- **Candidati (codice)**: ricette del ricettario e/o dei ricettari PDF scelti,
  senza quelle che toccano un'allergia o un'intolleranza, senza i tag esclusi e
  solo con quelli inclusi se indicati; le antipatie restano ma segnate.
- **Settimana (LLM)**: il profilo ridotto (niente nome, email, data di
  nascita), le candidate numerate, i pasti con i giorni di attesa; risponde con
  un numero di candidata o il titolo di una ricetta nuova per ogni pasto.
- **Ricette nuove (LLM)**: scritte per intero col divieto esplicito degli
  allergeni, salvate fuori dal ricettario (`source=plan`, bozza) e
  **ricontrollate sugli ingredienti veri**: se toccano un divieto si buttano e
  il pasto resta da scegliere.
- **Controlli (codice)**: una ricetta che non regge l'attesa in frigo si
  cucina il giorno stesso, con una nota.

"Cosa cucini" non è un modello: sono i pasti raggruppati per `cooked_on`. Il
piano nasce bozza; "Attiva" lo rende quello in uso (gli altri attivi si
archiviano) e lo mostra in "Oggi". I pasti si cambiano a mano (ricetta,
porzioni, pasto libero).

**Perché:** le regole che proteggono (allergie, conservazione) non possono
dipendere da un prompt; la varietà e l'equilibrio sì. Una settimana per
chiamata tiene il prompt corto e il mese comunque coerente (le settimane dopo
sanno cosa c'era prima).

**Costo accettato:** niente calorie né macro (piano qualitativo, progettazione
§9); niente guida passo passo delle sessioni di prep e niente "rigenera solo
questo pasto" con l'LLM per ora; il piano del nutrizionista con grammature e
frequenze arriva in fase 7.

**Quando rivederla:** con il piano del nutrizionista le sue regole diventano
vincoli del passo "settimana"; se servono le calorie, una tabella nutrizionale
per ingrediente nel catalogo.
