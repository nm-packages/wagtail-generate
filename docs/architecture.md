# Architecture

The CLI layer parses user-facing options and delegates generation to typed,
independently testable planning and execution code. Generated project content
and tooling configuration live under `src/wagtail_generate/templates/`; Python
orchestrates resource loading and rendering rather than embedding large file
strings.

## Module boundaries

| Module | Responsibility |
| --- | --- |
| `cli.py` | Parse options and enforce the ordinary generation boundary. |
| `planning.py` | Build typed project, dependency, command, and file plans. |
| `commands.py` | Run external commands and translate operational failures. |
| `generation.py` | Resolve versions, execute plans, configure projects, and publish them. |
| `transformations.py` | Adapt Wagtail output for source-subfolder layouts. |
| `rendering.py` | Load, render, validate, and write packaged templates. |
| `developer_tools.py` | Plan database, Docker, formatter, and development tooling files. |
| `playground.py` | Rebuild and serve the disposable in-checkout site. |
| `safety.py` | Validate source packages, checkout boundaries, and destinations. |

## Generation boundary

Build and validate a complete generation plan before writing to the destination.
Refuse to overwrite existing files without explicit opt-in, and check the
source-checkout restriction before creating directories or running external
commands.

Generation runs in staging and publishes only after the complete sequence
succeeds. Floating Python and package choices are resolved before final output,
recorded in the plan and lock files, and rendered deterministically for those
inputs. A failed command stops the sequence and does not publish a partial
project.

Keep template rendering separate from side effects such as UV, Django, Git, or
frontend commands. Keep generated Docker, Compose, database settings, formatter
configuration, and project guidance consistent with the selected database and
source layout.

The generator has one tooling and template set. `--site-directory` selects where
Wagtail source lives; `--template` supplies a custom Wagtail start template.
Wagtail is installed into each generated project's environment rather than into
the generator's runtime environment. Prefer the standard library over adding a
runtime dependency.

Implementation-level details belong in module docstrings, focused comments, and
regression tests. In particular, keep import-rewriting rules, cleanup safety,
staging order, and model/template compatibility constraints close to the code
that enforces them.
