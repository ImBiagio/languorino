# 0019 — Piano condiviso in sola lettura

Un utente fa vedere il suo piano a un altro account scrivendone l'email
(`POST /api/plan-shares`, modello `plans.PlanShare` owner → viewer). Chi
riceve vede **il piano di oggi** di chi condivide (`current_plan`, lo stesso
della home), sempre com'è adesso, e le ricette che ci sono dentro. Non lo
può cambiare, non ci fa la spesa e non lo copia: il suo piano se lo crea da
sé (`apps/plans/sharing.py`).

- Si condivide la persona, non un piano: quando chi condivide attiva un
  piano nuovo, chi riceve vede quello.
- Chi riceve ha un'API sua (`GET /api/plan-shares/{id}/plan` e
  `…/recipes/{recipe_id}`). Le API del piano e delle ricette restano del
  proprietario, così niente di quello che modifica è raggiungibile.
- Del piano si vedono pasti, grammature a porzione, giorni di cottura,
  porzioni, pasti al giorno e modo del prep. Non si vedono l'obiettivo, le
  note per il generatore e il piano del nutrizionista. Delle ricette solo
  quelle che sono nel piano adesso.
- Chi riceve ha una mail con il link alla pagina `/piano/condivisi/<id>`.
  Trova i piani che riceve sotto il suo, in "Piani che ti fanno vedere".
- Chi condivide toglie una persona quando vuole; chi riceve può togliere un
  piano dal suo elenco. Non si condivide con sé stessi né due volte.
- Serve un account: l'email di chi non ce l'ha risponde 400. Questo dice se
  un'email è registrata, quindi i tentativi hanno un limite loro (`invites`,
  20 all'ora).

**Perché:** in famiglia o in coppia serve vedere cosa mangia l'altro senza
mescolare i piani. Ognuno ha profilo, allergie e obiettivi suoi; un piano in
comune o modificabile da due persone avrebbe chiesto di decidere di chi sono
quelle regole.

**Costo accettato:**
- Non c'è un invito per chi non ha un account.
- Chi riceve non può copiare il piano né mettere le ricette dell'altro nel
  suo ricettario da qui.
- L'email nel form rivela se esiste un account.

**Quando rivederla:** se serve un piano davvero comune (una spesa per tutta
la casa, porzioni per più persone con profili diversi).
