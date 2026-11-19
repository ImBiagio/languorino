# 0024 — Ricorrenti della spesa, suggeriti dal piano alimentare

La spesa ha due parti: quello che serve per i pasti della preparazione (ADR
0008, 0023) e i **ricorrenti**, cioè cose che si comprano sempre anche se la
preparazione non le mette nei giorni. Esempi: la colazione tolta dal piano, le
merende, il caffè, il detersivo. I ricorrenti sono dell'utente
(`shopping.RecurringItem`) e si scelgono in `/spesa/ricorrenti`. Ognuno ha nome,
quantità per volta per tutta la casa (facoltativa), volte a settimana (1–21) e
un interruttore "in spesa". Ha anche il pasto da cui viene, se è suggerito.

Una lista li vuole o no (`ShoppingList.include_recurring`). Dal piano parte con
i ricorrenti accesi, la lista vuota senza. Sulla lista c'è un interruttore che
li aggiunge o li toglie subito. Nella lista ogni ricorrente vale
`quantità × volte × giorni / 7`. Si somma alle voci dei pasti con la stessa
conversione di unità (`build_items(meals, extras)`): lo yogurt della colazione
e quello del pranzo fanno una voce sola. Quello che il catalogo non conosce
(detersivo) resta una voce a sé in "Altro". Le fonti della voce hanno
`recurring: true` e l'icona dei ricorrenti. Il ricalcolo rifà anche i
ricorrenti e funziona pure su una lista senza piano.

I **suggerimenti** (`shopping/recurring.py`, tutto codice, niente LLM) vengono
dal piano alimentare della preparazione attiva, o dall'ultimo confermato.
Prendono solo i pasti che la preparazione non prepara: senza preparazione,
colazione e spuntini. Ogni opzione si divide negli alimenti
("200 g yogurt + 30 g avena") e si legge con le grammature
(`parse_equivalent`). Si tolgono le misure dopo la barra ("150 g / 1 Frutto
medio Frutta fresca" → frutta fresca 150 g), le misure davanti ("1 tazza di
latte" → latte, 1 tazza) e "a volontà". La quantità è moltiplicata per le
persone di casa. Le volte a settimana dividono i 7 giorni fra le opzioni del
pasto: con 3 colazioni diverse ognuna vale 2 volte, e un alimento presente in
più opzioni somma le volte. L'utente spunta quali aggiungere e poi può
cambiare tutto.

**Perché:** chi toglie la colazione dalla preparazione la mangia lo stesso e
deve comprarla. Prima l'unico modo era scriverla a mano a ogni lista. Si è
scartato "metti la colazione nella preparazione ma senza mostrarla". La
preparazione deciderebbe cosa mangi ogni mattina e la generazione costerebbe
di più. A colazione, poi, si ruota fra poche cose sempre uguali, e decidere
le volte a settimana basta. Le volte a settimana, invece di una quantità
settimanale, tengono la grammatura del piano leggibile ("200 g, 4 volte") e
scalano da sole con i giorni della lista.

**Costo accettato:**

- Le volte suggerite sono una stima (7 diviso le opzioni) e non sanno quale
  colazione farai davvero.
- Le misure scritte in modi strani possono dare nomi da correggere a mano
  ("cereali da colazione, al naturale").
- Un ricorrente cambiato non aggiorna le liste già fatte finché non si
  ricalcolano.
- Se colazione e preparazione contengono lo stesso alimento, la spesa lo
  somma. È giusto, ma non si vede quanto viene da dove, se non nelle fonti.

**Quando rivederla:** se servono ricorrenti con un ritmo diverso dalla
settimana (es. ogni mese il detersivo) o legati a un giorno preciso; se la
preparazione torna a includere colazione e merende per tutti.
