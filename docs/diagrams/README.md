# Diagrams

Generated with [Archify](https://github.com/tt-a1i/archify). Every component cites the source
lines it was drawn from: the architecture and ask diagrams at commit `ceea036`, the chat
diagram at `b148fc8`.

| File | What it is |
|---|---|
| `architecture.light.svg`, `architecture.dark.svg` | Production architecture, embedded in the main README |
| `ask-sequence.light.svg`, `ask-sequence.dark.svg` | How one question is answered, embedded in the main README |
| `chat-sequence.light.svg`, `chat-sequence.dark.svg` | How one chat turn is answered, embedded in the main README |
| `architecture/architecture.html`, `ask-sequence/ask-sequence.html`, `chat-sequence/chat-sequence.html` | Interactive versions: download and open in a browser to search, focus, and follow source links |
| `architecture/candidate.json`, `ask-sequence/candidate.json`, `chat-sequence/candidate.json` | The diagram sources |

## Regenerating after a code change

1. Edit the `candidate.json`: set `meta.repository.revision` to the new commit (it must be
   pushed, or the source links won't resolve) and fix any `sources` line ranges that moved.
2. From the repository root, run:

   ```bash
   node <archify>/bin/archify.mjs finalize architecture docs/diagrams/architecture/candidate.json docs/diagrams/architecture/architecture.html --repo-root . --quality showcase
   ```

   Use `sequence` and the `ask-sequence` or `chat-sequence` paths for the other diagrams. `finalize` checks
   every source reference against that commit and renders the page in headless Chrome.
3. Open the HTML, choose **Export → SVG · Light** and **Export → SVG · Dark**, and save
   them over the SVGs in this folder.

The check receipts and screenshots that `finalize` writes are git-ignored because they
contain local paths.
