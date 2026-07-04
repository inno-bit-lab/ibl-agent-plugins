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
- `plugins/ibl-agent-workflow` - skill di workflow cross-agent: scrivere un documento di handoff di sessione (redatto, salvato nella temp dir del SO) perché un agente fresco possa continuare il lavoro.

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

Quando la skill è installata in Codex, Claude Code, Antigravity o OpenCode,
l'area di installazione è solo una cache. Gli improvement devono comunque essere
scritti nel checkout Git canonico. Il marketplace non imposta automaticamente
`IBL_AGENT_PLUGINS_HOME`: quella variabile è solo un override opzionale per path
non standard.

Il helper `skills/skill-improvement/scripts/improvement_inbox.py` cerca il
checkout tramite directory corrente, path standard sotto
`%USERPROFILE%\agent-marketplaces\`, installazioni linkate e, se configurato,
`IBL_AGENT_PLUGINS_HOME`. Se non trova il checkout, mostra il comando `gh repo
clone` da eseguire una volta.

Su GitHub il flusso previsto è:

```text
skill fallisce
  -> artifact in improvements/inbox
  -> branch proposal-only
  -> PR proposal-only
  -> process/apply PR
  -> review e validazione della modifica applicata
  -> merge
  -> update degli agent dal repo
```

In Capture Mode l'agent che propone l'improvement deve pubblicare la richiesta,
non applicarla automaticamente:

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py publish improvements/inbox/<artifact-id> --create-pr
```

Questa operazione committa e pusha solo `improvements/inbox/<artifact-id>/`.
Le modifiche reali sotto `plugins/` sono responsabilità del passaggio Process
Mode, che può essere eseguito da un altro agent o maintainer.

Gli artifact applicati vengono spostati in `improvements/applied/`. Gli artifact
non validi o superati vengono spostati in `improvements/rejected/`.

## Aggiornamento

Il canale di update del team è GitHub. Se il repo è già clonato, il fallback
manuale resta:

```powershell
cd "$env:USERPROFILE\agent-marketplaces\ibl-agent-plugins"
git pull --ff-only
```

Con il plugin `ibl-skill-improvement` installato, l'utente può invece chiedere
all'agent di aggiornare i plugin IBL senza ricordare la cartella. La skill
`agent-plugin-update` usa questo helper:

```powershell
python plugins/ibl-skill-improvement/skills/agent-plugin-update/scripts/update_agent_plugins.py --validate
```

L'helper cerca il checkout tramite directory corrente, path standard sotto
`%USERPROFILE%\agent-marketplaces\`, installazioni linkate di Antigravity,
Claude Code o OpenCode e, se configurato, `IBL_AGENT_PLUGINS_HOME`.

Per Codex, se il marketplace è stato aggiunto direttamente da GitHub:

```powershell
codex plugin marketplace add inno-bit-lab/ibl-agent-plugins --ref main
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

### Codex

Installazione da marketplace GitHub:

```powershell
codex plugin marketplace add inno-bit-lab/ibl-agent-plugins --ref main
codex plugin add ibl-abp@ibl-agent-plugins
codex plugin add ibl-skill-improvement@ibl-agent-plugins
codex plugin add ibl-agent-workflow@ibl-agent-plugins
```

Aggiornamento:

```powershell
codex plugin marketplace upgrade
codex plugin add ibl-abp@ibl-agent-plugins
codex plugin add ibl-skill-improvement@ibl-agent-plugins
codex plugin add ibl-agent-workflow@ibl-agent-plugins
```

Disinstallazione:

```powershell
codex plugin remove ibl-abp@ibl-agent-plugins
codex plugin remove ibl-skill-improvement@ibl-agent-plugins
codex plugin remove ibl-agent-workflow@ibl-agent-plugins
codex plugin marketplace remove ibl-agent-plugins
```

Installazione locale dal checkout, utile per sviluppo:

```powershell
python tools/install-plugin.py codex --plugin ibl-abp --scope workspace
python tools/install-plugin.py codex --plugin ibl-skill-improvement --scope workspace
python tools/install-plugin.py codex --plugin ibl-agent-workflow --scope workspace
```

### Claude Code

Installazione da marketplace GitHub:

```powershell
claude plugin marketplace add inno-bit-lab/ibl-agent-plugins
claude plugin install ibl-abp@ibl-agent-plugins
claude plugin install ibl-skill-improvement@ibl-agent-plugins
```

Aggiornamento:

```powershell
claude plugin marketplace update ibl-agent-plugins
claude plugin update ibl-abp@ibl-agent-plugins
claude plugin update ibl-skill-improvement@ibl-agent-plugins
```

Disinstallazione:

```powershell
claude plugin uninstall ibl-abp@ibl-agent-plugins -y
claude plugin uninstall ibl-skill-improvement@ibl-agent-plugins -y
claude plugin marketplace remove ibl-agent-plugins
```

Installazione locale dal checkout, utile per sviluppo:

```powershell
python tools/install-plugin.py claude --plugin ibl-abp --scope workspace
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

Disinstallazione globale:

```powershell
Remove-Item -LiteralPath "$env:USERPROFILE\.gemini\config\plugins\ibl-abp" -Force
Remove-Item -LiteralPath "$env:USERPROFILE\.gemini\config\plugins\ibl-skill-improvement" -Force
```

Disinstallazione workspace:

```powershell
Remove-Item -LiteralPath "C:\projects\my-abp-project\.agents\plugins\ibl-abp" -Force
Remove-Item -LiteralPath "C:\projects\my-abp-project\.agents\plugins\ibl-skill-improvement" -Force
```

### OpenCode

OpenCode consuma le singole skill. Installazione globale:

```powershell
python tools/install-plugin.py opencode --plugin ibl-abp --scope global --strategy link
python tools/install-plugin.py opencode --plugin ibl-skill-improvement --scope global --strategy link
```

Installazione workspace:

```powershell
python tools/install-plugin.py opencode --plugin ibl-abp --scope workspace --workspace C:\projects\my-abp-project --strategy link
python tools/install-plugin.py opencode --plugin ibl-skill-improvement --scope workspace --workspace C:\projects\my-abp-project --strategy link
```

Disinstallazione globale:

```powershell
Remove-Item -LiteralPath "$env:USERPROFILE\.config\opencode\skills\abp-core" -Force
Remove-Item -LiteralPath "$env:USERPROFILE\.config\opencode\skills\abp-feature-dev" -Force
Remove-Item -LiteralPath "$env:USERPROFILE\.config\opencode\skills\abp-mongodb" -Force
Remove-Item -LiteralPath "$env:USERPROFILE\.config\opencode\skills\abp-multitenancy" -Force
Remove-Item -LiteralPath "$env:USERPROFILE\.config\opencode\skills\abp-react-ui" -Force
Remove-Item -LiteralPath "$env:USERPROFILE\.config\opencode\skills\abp-testing" -Force
Remove-Item -LiteralPath "$env:USERPROFILE\.config\opencode\skills\agent-plugin-update" -Force
Remove-Item -LiteralPath "$env:USERPROFILE\.config\opencode\skills\skill-improvement" -Force
```

Disinstallazione workspace:

```powershell
Remove-Item -LiteralPath "C:\projects\my-abp-project\.opencode\skills\abp-core" -Force
Remove-Item -LiteralPath "C:\projects\my-abp-project\.opencode\skills\abp-feature-dev" -Force
Remove-Item -LiteralPath "C:\projects\my-abp-project\.opencode\skills\abp-mongodb" -Force
Remove-Item -LiteralPath "C:\projects\my-abp-project\.opencode\skills\abp-multitenancy" -Force
Remove-Item -LiteralPath "C:\projects\my-abp-project\.opencode\skills\abp-react-ui" -Force
Remove-Item -LiteralPath "C:\projects\my-abp-project\.opencode\skills\abp-testing" -Force
Remove-Item -LiteralPath "C:\projects\my-abp-project\.opencode\skills\agent-plugin-update" -Force
Remove-Item -LiteralPath "C:\projects\my-abp-project\.opencode\skills\skill-improvement" -Force
```

## Validazione

Prima di proporre o mergiare modifiche:

```powershell
python tools/validate-plugin.py
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py list
```

Se il repo canonico non è nella directory corrente:

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py list --repo "$env:USERPROFILE\agent-marketplaces\ibl-agent-plugins"
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
