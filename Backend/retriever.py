class Retriever:
    def __init__(self):
        self.docs = []

    def add(self, doc):
        self.docs.append(doc)

    def get_top(self, k=5):
        return self.docs[:k]

retriever = Retriever()
