---
tags: [{{project}}, convenzioni]
---
# Convenzioni

↩ [[{{Project}}]]

## Commit
- **In inglese**, una riga breve che inizia con `Add`, `Up`, `Fix` o `Delete` + cosa è cambiato (es. `Fix login redirect loop`, `Add CSV export`)
- Commit e push **sempre** a fine modifica, senza aspettare che venga chiesto
- **Mai** `Co-Authored-By` di Claude
- Regola scritta anche in `CLAUDE.md` del repo (che è in `.gitignore`), dal template [templatino](https://github.com/ImBiagio/templatino)

## Flusso git
- `main` è il branch di default
- **Ogni feature nuova** su un branch `feature/<nome-feature>` (kebab-case, in inglese, es. `feature/csv-export`) aperto da `main` aggiornato; commit e push lì, merge in `main` quando la feature è confermata finita
- Fix e piccole modifiche (doc, config) direttamente su `main`

## Knowledge base
- A ogni modifica aggiornare **sempre** le note toccate + [[Storico]] e [[TODO e idee]]
- Nuove credenziali/accessi → [[Credenziali e accessi]] subito

## Codice
- Commenti e docstring **in italiano**, spiegano il perché

## Lavorare con Claude
- Contesto: questo vault + `README.md` + `CLAUDE.md`
- Sul Mac niente runtime locali: test e build via Docker
