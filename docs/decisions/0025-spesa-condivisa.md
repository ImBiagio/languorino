# 0025 — Spesa condivisa con chi vede il piano

Chi riceve un piano condiviso (ADR 0019, `plans.PlanShare` owner → viewer)
usa anche le liste della spesa di chi glielo fa vedere. Le vede in Spesa, le
spunta, aggiunge e modifica voci, le ricalcola e le chiude, come chi le ha
fatte. Tutto passa da `shopping.views.lists_of(user)`: le liste proprie più
quelle dei `PlanShare` dove `user` è viewer. Non c'è un modello nuovo, e la
condivisione si accende e si spegne insieme a quella del piano.

- Eliminare la lista resta di chi l'ha fatta (403 per l'altro). Lo stesso
  vale per scegliere i ricorrenti (ADR 0024): sono suoi, e la lista usa i
  suoi. L'altro può solo accenderli o spegnerli sulla lista.
- Una voce aggiunta dall'altro si abbina al catalogo di chi ha fatto la
  lista, così il reparto è lo stesso per tutti e due.
- Le API della lista hanno `shared_by`, il nome di chi l'ha fatta se non è
  mia (null se è mia). L'interfaccia scrive "Lista di X, la fate insieme",
  nasconde il cestino e il link ai ricorrenti e mostra le altre liste aperte.
  Con la propria e quella dell'altro la home apre solo la più nuova.
- Una lista aperta si ricarica da sola ogni 15 secondi, così le spunte
  dell'altro arrivano anche mentre si è al supermercato in due.
- Si condivide in un verso solo, come il piano: le liste di chi riceve
  restano sue finché non condivide anche lui.

**Perché:** in coppia o in famiglia la spesa è una sola, anche quando i piani
sono due. Prima chi riceveva il piano doveva farsi mandare la lista a parte.
Si è scartato un modello di condivisione per ogni lista: chiede un secondo
invito per una cosa che va sempre insieme al piano. Si è scartata anche una
copia della lista nell'account dell'altro: due copie non si spuntano insieme.

**Costo accettato:**

- Chi condivide il piano condivide per forza anche la spesa. Non si sceglie
  separatamente.
- Le spunte arrivano con un ritardo fino a 15 secondi, non in tempo reale.
- Se tutti e due hanno una lista aperta, la home apre la più nuova. L'altra
  si raggiunge da "Altre liste aperte".

**Quando rivederla:** se serve condividere la spesa senza il piano o
viceversa; se serve vedere le spunte all'istante (WebSocket); se la casa
diventa un oggetto con più membri invece di coppie owner → viewer.
