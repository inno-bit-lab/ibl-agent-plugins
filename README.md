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
- `plugins/ibl-skill-improvement` - skill per catturare, revisionare e applicare improvement alle skill aziendali.

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
