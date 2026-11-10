#!/usr/bin/env bash
# Trasforma una copia di templatino in un progetto nuovo:
#   - rinomina templatino/Templatino/TEMPLATINO nel nome del progetto
#   - porte locali (app, API, Postgres) e dominio di produzione
#   - CLAUDE.md dal modello in .template/ (in .gitignore: ha percorsi del Mac)
#   - cartella del progetto nel vault Obsidian Dev/, dalle note di .template/vault
#   - toglie dal README la parte sul template, poi cancella .template/ e se stesso
#
# Uso (dalla radice del repo appena creato da template):
#   scripts/init-project.sh <nome> --app 5177 --api 8030 --db 5437 \
#       [--domain languor.inoo.it] [--vault Languorino] [--no-vault]
#
# Il dominio di default e' <nome senza "ino">.inoo.it, come sold/regal/cinem.
# Il vault si sceglie con DEV_VAULT (default: il vault Dev su Google Drive).

set -euo pipefail

usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

[[ $# -ge 1 ]] || usage
name="$1"; shift
[[ "$name" =~ ^[a-z][a-z0-9]*$ ]] || { echo "Nome non valido: solo minuscole e cifre" >&2; exit 1; }

port_app="" port_api="" port_db="" domain="" vault_name="" with_vault=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --app) port_app="$2"; shift 2 ;;
    --api) port_api="$2"; shift 2 ;;
    --db) port_db="$2"; shift 2 ;;
    --domain) domain="$2"; shift 2 ;;
    --vault) vault_name="$2"; shift 2 ;;
    --no-vault) with_vault=0; shift ;;
    *) usage ;;
  esac
done
[[ -n "$port_app" && -n "$port_api" && -n "$port_db" ]] || {
  echo "Servono --app, --api e --db (porte libere, diverse dagli altri progetti)" >&2; exit 1; }

root="$(git rev-parse --show-toplevel)"
cd "$root"
[[ -d .template ]] || { echo "Niente .template/: progetto gia' inizializzato?" >&2; exit 1; }

Name="$(printf '%s' "${name:0:1}" | tr '[:lower:]' '[:upper:]')${name:1}"
NAME="$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')"
domain="${domain:-${name%ino}.inoo.it}"
vault_name="${vault_name:-$Name}"
DEV_VAULT="${DEV_VAULT:-$HOME/Library/CloudStorage/GoogleDrive-caracciolo.biagio1996@gmail.com/Il mio Drive/DriveSyncFiles/Dev}"
vault_dir="$DEV_VAULT/$vault_name"
today="$(date +%F)"
local_dir="${root/#$HOME/~}"

export P_NAME="$name" P_Name="$Name" P_NAME_UP="$NAME" P_DOMAIN="$domain" \
  P_APP="$port_app" P_API="$port_api" P_DB="$port_db" \
  P_VAULT="$vault_dir" P_VAULT_NAME="$vault_name" P_DATE="$today" P_LOCAL="$local_dir"

# --- nomi, dominio e porte in tutti i file di testo tracciati ---
# git grep -I salta i binari (.mo, immagini).
git grep -l -z -I -E 'templatino|Templatino|TEMPLATINO|templat\.inoo\.it|5190|8090|5490' \
  -- . ':!.template' ':!scripts/init-project.sh' |
  xargs -0 perl -pi -e '
    s/templat\.inoo\.it/$ENV{P_DOMAIN}/g;
    s/templatino/$ENV{P_NAME}/g; s/Templatino/$ENV{P_Name}/g; s/TEMPLATINO/$ENV{P_NAME_UP}/g;
    s/\b5190\b/$ENV{P_APP}/g; s/\b8090\b/$ENV{P_API}/g; s/\b5490\b/$ENV{P_DB}/g;'
echo "+ nome $name, dominio $domain, porte $port_app/$port_api/$port_db"

# --- README: via la parte che spiega il template ---
perl -0pi -e 's/<!-- template:start -->.*?<!-- template:end -->\n*//s' README.md

# --- CLAUDE.md (in .gitignore) ---
render() {
  perl -pe 's/\{\{project\}\}/$ENV{P_NAME}/g; s/\{\{Project\}\}/$ENV{P_VAULT_NAME}/g;
            s/\{\{vault_dir\}\}/$ENV{P_VAULT}/g; s/\{\{date\}\}/$ENV{P_DATE}/g;
            s/\{\{local_dir\}\}/$ENV{P_LOCAL}/g; s/\{\{port_app\}\}/$ENV{P_APP}/g;
            s/\{\{port_api\}\}/$ENV{P_API}/g; s/\{\{port_db\}\}/$ENV{P_DB}/g' "$1"
}
if [[ -e CLAUDE.md ]]; then
  echo "· CLAUDE.md esiste gia', non lo tocco"
else
  render .template/CLAUDE.md.template > CLAUDE.md
  echo "+ CLAUDE.md"
fi

# --- vault Obsidian ---
if [[ $with_vault == 1 ]]; then
  if [[ ! -d "$DEV_VAULT" ]]; then
    echo "! vault non trovato ($DEV_VAULT): salto. Rilancia con DEV_VAULT o usa --no-vault" >&2
  else
    mkdir -p "$vault_dir"
    for tpl in .template/vault/*.md; do
      note="$(basename "$tpl")"
      [[ "$note" == "_Indice.md" ]] && note="$vault_name.md"
      if [[ -e "$vault_dir/$note" ]]; then
        echo "· vault/$vault_name/$note esiste gia'"
      else
        render "$tpl" > "$vault_dir/$note"
        echo "+ vault/$vault_name/$note"
      fi
    done
    home="$DEV_VAULT/Home.md"
    if [[ -f "$home" ]] && ! grep -qF "[[$vault_name]]" "$home"; then
      # La lista dei progetti finisce alla prima riga vuota dopo "## Progetti".
      perl -0pi -e 's/(## Progetti\n(?:- .*\n)*)/$1- [[$ENV{P_VAULT_NAME}]] — descrizione da scrivere\n/' "$home"
      echo "+ [[$vault_name]] in Home.md"
    fi
  fi
fi

# --- pulizia: il template ha finito il suo lavoro ---
git rm -rq .template scripts/init-project.sh
rmdir scripts 2>/dev/null || true

echo
echo "Fatto. Ora:"
echo "  1. cp .env.example .env && docker compose up --build   (app su http://localhost:$port_app)"
echo "  2. palette: rigenera i token in frontend/src/index.css dal colore seed del progetto"
echo "  3. logo e icone in frontend/public/, descrizione in README e nel vault"
echo "  4. git add -A && git commit -m \"Add $name from templatino\" && git push"
