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


COMMAND_PROMPTS = {
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
    Ты ИИ-агент с доступом в систему в режиме {mode}.
    Отвечай строго в формате JSON для запуска нужных скриптов.

    Правила:
    - Всегда возвращай только один JSON-объект без markdown, пояснений и лишнего текста.
    - Для выбора следующего действия используй поле `command`.
    - Если нужно выполнить системную команду, выбирай только из списка доступных команд ниже.
    - Если задача завершена, используй команду `done` и передай итог пользователю в `result`.
    - Не выдумывай команды вне списка.
    - Если `writefile` недоступен в текущем режиме, не используй его.

    У тебя есть следующие команды:

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
