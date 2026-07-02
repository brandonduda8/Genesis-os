class Mailbox:

    def __init__(self):
        self.messages = []

    def receive(self, message):
        self.messages.append(message)

    def unread(self):
        return self.messages

    def clear(self):
        self.messages.clear()
