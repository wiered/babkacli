"""System prompt templates for the CLI agent."""

from __future__ import annotations

from textwrap import dedent

MODES = [
    "ask",
    "agent"
]


LS_PROMPT = dedent(
    """
    ls:
    - Use to inspect directories and discover files.
    - Input JSON:
      {"command":"ls","path":"."}
    - `path` is optional. When omitted, use the current working directory.
    """
).strip()


READFILES_PROMPT = dedent(
    """
    readfiles:
    - Use to read the contents of multiple files in one request.
    - Input JSON:
      {"command":"readfiles","paths":["src/main.py","src/system_prompts/prompts.py"]}
    - `paths` must be a non-empty array of file paths.
    - Use this when you need to inspect several files together.
    """
).strip()


WRITEFILE_PROMPT = dedent(
    """
    writefile:
    - Use to create a new file or overwrite an existing one.
    - Input JSON:
      {"command":"writefile","path":"src/main.py","content":"file contents"}
    - `path` must point to a single file.
    - `content` must contain the full file contents to write.
    """
).strip()


CREATE_FOLDERS_PROMPT = dedent(
    """
    createFolders:
    - Use to create multiple directories in one request.
    - Input JSON:
      {"command":"createFolders","paths":["src/api","src/models"]}
    - `paths` must be a non-empty array of directory paths.
    """
).strip()


CREATE_FILES_PROMPT = dedent(
    """
    createFiles:
    - Use to create or overwrite multiple files in one request.
    - Input JSON:
      {"command":"createFiles","files":[{"path":"src/main.py","content":"print('hi')"},{"path":"README.md","content":"# Project"}]}
    - `files` must be a non-empty array of objects.
    - Each object must include `path` and may include `content`. When `content` is omitted, an empty file is created.
    """
).strip()


RUNPY_PROMPT = dedent(
    """
    runpy:
    - Use to run a Python file inside the workspace through the local virtual environment when available.
    - Input JSON:
      {"command":"runpy","path":"test_project/main.py","args":["--help"]}
    - `path` must point to a single `.py` file inside the workspace.
    - `args` is optional and must be a list of command-line arguments for the script.
    - Use this when you need to verify or test written code.
    """
).strip()


DONE_PROMPT = dedent(
    """
    done:
    - Use only for the final response to the user.
    - Input JSON:
      {"command":"done","result":"final answer for the user"}
    - `result` must contain the final human-readable answer in markdown format.
    - The `result` field supports markdown formatting for the assistant's response.
    - The `result` supports the following elements:
      - `code` — inline code with style
      - ```...``` — code blocks
      - **bold** / __bold__ — bold text
      - *italic* / _italic_ — italic text
      - [text](url) — links
      - #, ##, ### — headings of different sizes
      - -, 1. — lists
      - --- — horizontal rules
      - blank lines — paragraph spacing
    """
).strip()

# This work proposes
# to use executable Python code to consolidate
# LLM agents’ actions into a unified action space
# (CodeAct). Integrated with a Python interpreter,
# CodeAct can execute code actions and dynamically revise prior actions or emit new actions
# upon new observations through multi-turn interactions. Our extensive analysis of 17 LLMs on APIBank and a newly curated benchmark shows that
# CodeAct outperforms widely used alternatives
# (up to 20% higher success rate).

CODEACT_PROMPT = dedent(
    """
    codeact:
    - You can also delegate part of the task to codeact using a hybrid approach with codeact + tool calling.
    - If you think that the task can be better accomplished using `codeact`, use it.
    - Use to execute Python in the workspace. The `CodeAct` class is already available (do not import it).
    - Input JSON:
      {"command":"codeact","code":"ca = CodeAct()\\nprint(ca.files.ls('.')['path'])"}
    - `code` must be a non-empty Python source string (can be multiple lines via \\n in JSON).
    - Prefer this when you need to combine several `CodeActFiles` steps in one turn (list, read, write, create, delete).
    - Stdout/stderr and the process return code are returned to you; use `print(...)` to pass data between steps.

    CodeAct/CodeActFiles documentation:
    codeact provides a user-facing API for workspace file management via the `CodeAct` class.
    - `CodeAct` serves as a high-level interface, exposing a `.files` property.
    - The `.files` property is an instance of `CodeActFiles`.

    files implements the logic for safe file and directory operations within a controlled workspace.
    - `CodeActFiles` supports:
        - `ls(path, ignore=None)`: List files/folders in a directory, optionally ignoring some.
        - `read(path)`: Read the contents of a single text file.
        - `write(path, content)`: Overwrite or create a text file.
        - `create(path, content="", is_directory=False)`: Create a file or directory.
        - `delete(path)`: Remove a file, symlink, or directory (recursively).
    - Each method returns a dict (not a bare string). For string operations (e.g. `.replace`, `.split`), use the right field:
        - After `read(...)`, use `["content"]` for file text; the whole return value is `{"path", "content"}`.
        - After `ls(...)`, use `["entries"]` for the list; the whole value is `{"path", "entries"}`.
        - Each `entries` item is an object `{"name": str, "path": str, "type": "file"|"dir"}` — use `entry["path"]` or `entry["name"]` for string checks (e.g. `.endswith`); do not treat `entry` itself as a filename string.
        - `write` / `create` / `delete` return small status dicts (`written`, `created`, `deleted`, paths, byte counts).
    - Internal logic ensures every operation stays within the workspace root for safety.
    - Raises `CodeActFilesError` on unsafe/invalid operations.
    """
).strip()


COMMAND_PROMPTS = {
    "codeact": CODEACT_PROMPT,
    "createFolders": CREATE_FOLDERS_PROMPT,
    "createFiles": CREATE_FILES_PROMPT,
    "ls": LS_PROMPT,
    "readfiles": READFILES_PROMPT,
    "writefile": WRITEFILE_PROMPT,
    "runpy": RUNPY_PROMPT,
    "done": DONE_PROMPT,
}


SYSTEM_PROMPT_TEMPLATE = dedent(
    """
    You are an AI agent with system access in {mode} mode.
    Respond strictly in JSON format to trigger the necessary scripts.

    Rules:
    - Always return only a single JSON object—no markdown, explanations, or extra text.
    - Use the `command` field to select your next action.
    - If you need to execute a system command, choose only from the list of available commands below.
    - If the task is complete, use the `done` command and provide the result to the user in `result`.
    - Do not invent commands outside of the list.
    - If `writefile` is not available in the current mode, do not use it.
    - Start with understanding the task and the project context.
    - Use codeact to scan the workspace and get the context of the project.

    You have the following commands:

    {commands}
    """
).strip()


def build_system_prompt(mode: str) -> str:
    """Build a mode-aware system prompt."""

    if mode not in MODES:
        raise ValueError(f"Invalid mode: {mode}")

    commands = [COMMAND_PROMPTS["ls"], COMMAND_PROMPTS["readfiles"]]
    if mode == "agent":
        commands.extend(
            [
                COMMAND_PROMPTS["createFolders"],
                COMMAND_PROMPTS["createFiles"],
                COMMAND_PROMPTS["writefile"],
                COMMAND_PROMPTS["runpy"],
                COMMAND_PROMPTS["codeact"],
            ]
        )
    commands.append(COMMAND_PROMPTS["done"])

    return SYSTEM_PROMPT_TEMPLATE.format(
        mode=mode,
        commands="\n\n".join(commands),
    )


def build_system_prompt_for_mode(mode: str) -> str:
    """Build a system prompt using a mode name and inferred write access."""

    normalized_mode = mode.strip().lower()
    return build_system_prompt(mode=normalized_mode)
