from .files import CodeActFiles
from .search import CodeActSearch

class CodeAct:
    def __init__(self):
        self._files = CodeActFiles()
        self._search = CodeActSearch()

    @property
    def files(self) -> CodeActFiles:
        return self._files

    @property
    def search(self) -> CodeActSearch:
        return self._search