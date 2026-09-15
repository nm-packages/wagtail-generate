"""Plan and apply the opt-in starter homepage."""

import ast
from pathlib import Path

from wagtail_generate.rendering import RenderedFile, plan_template, write_rendered_files

HOME_TEMPLATE = Path("home/templates/home/home_page.html")
WELCOME_FILES = (
    Path("home/templates/home/welcome_page.html"),
    Path("home/static/css/welcome_page.css"),
)


def validate_homepage(source: Path) -> None:
    """Require the conventional homepage before replacing its presentation."""
    message = (
        "--starter-homepage requires home/models.py with a conventional HomePage "
        "and home/templates/home/home_page.html; preserve this template by "
        "answering no or passing --no-starter-homepage"
    )
    model = source / "home/models.py"
    if not model.is_file() or not (source / HOME_TEMPLATE).is_file():
        raise ValueError(message)
    try:
        tree = ast.parse(model.read_text())
    except SyntaxError as error:
        raise ValueError(message) from error
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "HomePage"
    ]
    if len(classes) != 1:
        raise ValueError(message)
    homepage = classes[0]
    if not any(
        isinstance(base, ast.Name) and base.id == "Page" for base in homepage.bases
    ):
        raise ValueError(message)
    for node in homepage.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in (
            "serve",
            "get_template",
            "get_context",
        ):
            raise ValueError(message)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id
                    in (
                        "template",
                        "ajax_template",
                    )
                    and (
                        not isinstance(node.value, ast.Constant)
                        or (node.value.value != "home/home_page.html")
                    )
                ):
                    raise ValueError(message)


def build_homepage_files(
    source_directory: str,
    enabled: bool,
) -> tuple[RenderedFile, ...]:
    """Render the homepage only when replacement was explicitly requested."""
    if not enabled:
        return ()
    source = Path(source_directory)
    return (
        plan_template(source / HOME_TEMPLATE, "homepage/home_page.html"),
        plan_template(
            source / "home/static/home/css/starter-homepage.css",
            "homepage/starter-homepage.css",
        ),
    )


def plan_homepage_removals(
    source_directory: str,
    enabled: bool,
) -> tuple[Path, ...]:
    """Limit cleanup to the files dedicated to Wagtail’s welcome screen."""
    if not enabled:
        return ()
    return tuple(Path(source_directory) / path for path in WELCOME_FILES)


def configure_homepage(
    directory: Path,
    source_directory: str,
    files: tuple[RenderedFile, ...],
    removals: tuple[Path, ...] = (),
) -> None:
    """Revalidate Wagtail output before replacing files inside staging."""
    if files:
        validate_homepage(directory / source_directory)
        for relative_path in removals:
            path = directory / relative_path
            if (
                relative_path.is_absolute()
                or ".." in relative_path.parts
                or any(
                    (directory / parent).is_symlink()
                    for parent in (relative_path, *relative_path.parents)
                )
                or (path.exists() and not path.is_file())
            ):
                raise ValueError(f"unsupported welcome-page cleanup path: {path}")
        write_rendered_files(directory, files)
        for relative_path in removals:
            (directory / relative_path).unlink(missing_ok=True)
