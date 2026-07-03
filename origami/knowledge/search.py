from .loader import KnowledgeLoader


class KnowledgeSearch:
    """
    Simple keyword search across Genesis knowledge documents.
    """

    def __init__(self):
        self.loader = KnowledgeLoader()
        self.documents = self.loader.read()

    def search(self, keyword):
        keyword = keyword.lower()
        results = {}

        for name, text in self.documents.items():
            if keyword in text.lower():
                results[name] = text

        return results
