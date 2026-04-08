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
    - Use only for the final user response.
    - Input JSON:
      {"command":"done","result":"final answer to the user"}
    - In the `result` field, write the final response in natural language using markdown (headings, lists, emphasis, links, code).

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
    - Python in workspace; `CodeAct` and `ca` (default instance) in scope (do not import). Stdout/stderr returned; use `print` when useful.
    - Input: {"command":"codeact","code":"..."} — non-empty source; multiline via \\n in JSON.
    - ca.files: ls(path, ignore=None); read(path); write(path, content); create(path, content="", is_directory=False); delete(path)
      Returns dicts: read→["content"]; ls→["entries"] as [{name,path,type}]; write/create/delete→status fields.
    - ca.search: search(pattern, path=".", max_matches=500, max_file_bytes=...); findfiles(pattern, path="."); readfolder(path=".", max_depth=8, max_entries=400)
    - CodeActFilesError | CodeActSearchError on invalid/unsafe paths.
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
    - Before executing any command, internally decide the next step based on current knowledge.
    - Do not execute commands blindly; prefer minimal necessary actions.
    - Use internal reasoning to decide next steps, but never include it in the output.
    - If a command fails, analyze the error and try an alternative approach.
    - Do not repeat the same failing command without changes.
    - Avoid repeating the same command with identical parameters.
    - If no progress is made after several steps, reassess the strategy.
    - Use `done` only when the task is fully completed and verified if needed.
    - Maintain an internal plan of actions and update it after each step.
    - Avoid re-reading files unless necessary.

    Start by inspecting the project structure using codeact.

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

if __name__ == "__main__":
    print(build_system_prompt_for_mode("agent"))
