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

**Aggiornamento 2026-11-11, "la sera cucino anche il pranzo dopo":** il pranzo
del giorno dopo è l'avanzo della cena, una sola cottura in doppia porzione.
Gemini sceglie solo le cene (e il primo pranzo del piano), che devono reggere
un giorno; il codice copia la cena nel pranzo dopo, anche a cavallo di due
settimane (`leftover_lunches`). Prima pranzo e cena si sceglievano come due
piatti diversi: la sera si cucinavano due cose e lo stesso piatto su due sere
di fila. Non vale con il piano del nutrizionista alla lettera, dove pranzo e
cena hanno opzioni diverse.

**Aggiornamento 2026-11-11, grammature, percentuale e cambio pasto:**
- Ogni pasto del piano porta `portion`: per ingrediente quanto mangia una
  persona (la ricetta divisa per le sue porzioni), senza "q.b." e
  facoltativi. Per pezzi e cucchiai c'è anche il peso o volume approssimato
  (grammi per pezzo del catalogo, 15 ml a cucchiaio). "Cosa cucini" mostra lo
  stesso per tutte le porzioni della sessione.
- "Nuovo piano" sceglie quante ricette nuove (`new_share`: 0, 25, 50, 75 o
  100% dei pasti). Il codice ne ricava quante ammetterne, mai sotto il minimo
  per variare, e lo dice all'LLM.
- Il cambio pasto sceglie dal ricettario, dai ricettari PDF o da due idee
  nuove scritte per quel pasto (`plans/swap.py`, modello veloce). Le idee non
  scelte e le ricette del piano rimaste senza pasto si cancellano dopo una
  settimana.

