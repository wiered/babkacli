from .files import CodeActFiles

class CodeAct:
    def __init__(self):
        self._files = CodeActFiles()

    @property
    def files(self) -> CodeActFiles:
        return self._files