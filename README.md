# IBL Agent Plugins

Repository sorgente per plugin e skill aziendali riusabili da agenti AI.

Questo repo è pensato per vivere su GitHub ed essere il punto canonico da cui
Codex, Claude Code, Antigravity e OpenCode ricevono plugin, skill e
miglioramenti.

## Principio

Il contenuto delle skill vive una sola volta:

```text
plugins/<plugin>/skills/<skill>/
```

Le piattaforme non devono mantenere testi divergenti. I manifest e gli script
sono adattatori per host diversi; il sorgente autorevole resta questo repo.

## Plugin disponibili

- `plugins/ibl-abp` - skill ABP Framework per backend .NET, MongoDB, multitenancy, React UI e test.
- `plugins/ibl-skill-improvement` - skill per catturare, revisionare, applicare improvement e aggiornare il checkout dei plugin aziendali.

## Layout

```text
.
├── .agents/plugins/marketplace.json      # marketplace Codex locale al repo
├── .claude-plugin/marketplace.json       # marketplace Claude Code locale al repo
├── improvements/                         # inbox degli improvement prodotti dagli agenti
├── plugins/
│   ├── ibl-abp/
│   │   ├── .codex-plugin/plugin.json     # manifest Codex
│   │   ├── .claude-plugin/plugin.json    # manifest Claude Code
│   │   ├── plugin.json                   # manifest Antigravity
│   │   └── skills/                       # sorgente unico delle skill
│   └── ibl-skill-improvement/
│       ├── .codex-plugin/plugin.json
│       ├── .claude-plugin/plugin.json
│       ├── plugin.json
│       └── skills/
└── tools/
```

## Packaging

Ogni plugin deve esporre, quando applicabile:

```text
plugins/<plugin>/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── plugin.json
└── skills/
```

OpenCode consuma direttamente le cartelle `skills/<skill>` tramite link o copia
controllata, senza duplicare il contenuto nel repository.

## Auto-improvement

Quando una skill sbaglia, l'agent deve creare una proposta versionata in:

```text
improvements/inbox/<id>/
```

La proposta contiene:

- `problem.md`
- `improvement.md`
- `modified-resources.md`
- `validation.md`
- `candidate/` opzionale con la versione migliorata dei file

Il plugin `ibl-skill-improvement` lavora questa inbox, revisiona la proposta e
applica le correzioni solo al sorgente canonico sotto `plugins/`.

Su GitHub il flusso previsto è:

```text
skill fallisce
  -> artifact in improvements/inbox
  -> branch/PR
  -> review e validazione
  -> merge
  -> update degli agent dal repo
```

Gli artifact applicati vengono spostati in `improvements/applied/`. Gli artifact
non validi o superati vengono spostati in `improvements/rejected/`.

## Aggiornamento

Il canale di update del team è GitHub. Se il repo è già clonato, il fallback
manuale resta:

```powershell
cd "$env:USERPROFILE\agent-marketplaces\ibl-agent-lugins"
git pull --ff-only
```

Con il plugin `ibl-skill-improvement` installato, l'utente può invece chiedere
all'agent di aggiornare i plugin IBL senza ricordare la cartella. La skill
`agent-plugin-update` usa questo helper:

```powershell
python plugins/ibl-skill-improvement/skills/agent-plugin-update/scripts/update_agent_plugins.py --validate
```

L'helper cerca il checkout tramite `IBL_AGENT_PLUGINS_HOME`, directory corrente,
path standard sotto `%USERPROFILE%\agent-marketplaces\`, e installazioni linkate
di Antigravity, Claude Code o OpenCode.

Per Codex, se il marketplace è stato aggiunto direttamente da GitHub:

```powershell
codex plugin marketplace add inno-bit-lab/ibl-agent-lugins --ref main
```

la snapshot Codex si aggiorna con:

```powershell
codex plugin marketplace upgrade
```

oppure tramite la skill:

```powershell
python plugins/ibl-skill-improvement/skills/agent-plugin-update/scripts/update_agent_plugins.py --codex-marketplace-upgrade
```

Questo non installa nuovi plugin e non sovrascrive copie installate. Per
installazioni fatte con link/junction il pull basta; per installazioni copiate
serve rilanciare `tools/install-plugin.py` con `--strategy copy --force`.

## Installazione

Questo repository non installa nulla automaticamente. Gli script sotto `tools/`
sono pensati per essere lanciati esplicitamente quando si vuole materializzare
il plugin o le skill in una piattaforma.

Esempi:

```powershell
python tools/install-plugin.py codex --plugin ibl-abp --scope workspace
python tools/install-plugin.py opencode --plugin ibl-abp --scope workspace
python tools/install-plugin.py claude --plugin ibl-skill-improvement --scope workspace
```

### Antigravity 2.0

Antigravity 2.0 supporta plugin custom come cartelle con `plugin.json`,
`skills/`, `rules/`, `mcp_config.json` e `hooks.json`.

Percorsi usati da Antigravity 2.0:

```text
<workspace-root>/.agents/plugins/<plugin-name>/   # workspace
<workspace-root>/_agents/plugins/<plugin-name>/   # workspace alternativo
~/.gemini/config/plugins/<plugin-name>/           # globale
```

Installazione workspace, consigliata per un progetto specifico:

```powershell
cd C:\projects\development\IBL\Ibl-ABP-Plugin

python tools/install-plugin.py antigravity --plugin ibl-abp --scope workspace --workspace C:\projects\my-abp-project --strategy link
python tools/install-plugin.py antigravity --plugin ibl-skill-improvement --scope workspace --workspace C:\projects\my-abp-project --strategy link
```

Questo crea:

```text
C:\projects\my-abp-project\.agents\plugins\ibl-abp
C:\projects\my-abp-project\.agents\plugins\ibl-skill-improvement
```

Installazione globale, disponibile in tutti i workspace Antigravity:

```powershell
cd C:\projects\development\IBL\Ibl-ABP-Plugin

python tools/install-plugin.py antigravity --plugin ibl-abp --scope global --strategy link
python tools/install-plugin.py antigravity --plugin ibl-skill-improvement --scope global --strategy link
```

Questo crea:

```text
%USERPROFILE%\.gemini\config\plugins\ibl-abp
%USERPROFILE%\.gemini\config\plugins\ibl-skill-improvement
```

Se Antigravity non mostra subito i plugin, riavvia Antigravity 2.0 o riapri il
workspace. Su Windows `--strategy link` prova prima un symlink e poi una
junction; usa `--strategy copy` se vuoi una copia congelata senza link al repo.

Per installazioni team/globali usare `--scope global` solo quando si vuole
aggiornare esplicitamente l'ambiente dell'agent.

## Validazione

Prima di proporre o mergiare modifiche:

```powershell
python tools/validate-plugin.py
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py list
```

Per validare i manifest Codex:

```powershell
python <plugin-creator>/scripts/validate_plugin.py plugins/ibl-abp
python <plugin-creator>/scripts/validate_plugin.py plugins/ibl-skill-improvement
```

## Convenzioni Per Agent

Le istruzioni repo-wide per gli agenti sono in:

```text
AGENTS.md
```

Il nome corretto è plurale: `AGENTS.md`.
