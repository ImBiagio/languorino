# 0002 — Profilo alimentare, allergeni UE e wizard a sezioni

Il profilo alimentare vive nell'app `profiles`: `Profile` (1:1 con `User`,
creato vuoto alla prima richiesta) e `FoodPreference` per gusti, antipatie,
allergie e intolleranze. Allergie e intolleranze si collegano, quando è
sicuro, a uno dei 14 allergeni UE (`profiles/allergens.py`): scelti dai chip,
o riconosciuti dal testo scritto a mano con parole chiave ed eccezioni note
("noce moscata", "latte di cocco"). Se il testo tocca più allergeni o nessuno,
l'allergene resta vuoto. Il wizard di onboarding e la pagina Profilo usano le
stesse sezioni (`frontend/src/features/profile/sections.tsx`).

**Perché:** i controlli di sicurezza del piano (progettazione, principio 2)
devono lavorare su codici, non su testo libero, e senza chiedere all'LLM. Le
sezioni condivise evitano che domande del primo accesso e modifica successiva
divergano. Le preferenze si salvano a ogni tocco e si cancellano davvero:
sono un elenco corrente, non storia.

**Costo accettato:** il riconoscimento per parole chiave non copre tutto (un
ingrediente raro scritto a mano resta senza allergene: vale come testo e il
piano lo confronterà per nome). `FoodPreference` non ha ancora la FK
all'ingrediente: arriva col catalogo degli ingredienti (fase 2).

**Quando rivederla:** quando c'è il catalogo ingredienti con gli allergeni,
le preferenze vanno collegate agli ingredienti e il riconoscimento per parole
chiave può diventare un ripiego.
