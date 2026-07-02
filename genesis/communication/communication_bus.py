from .mailbox import Mailbox

class CommunicationBus:

    def __init__(self):
        self.mailboxes = {}

    def register(self, agent_name):
        self.mailboxes[agent_name] = Mailbox()

    def send(self, message):
        if message.recipient in self.mailboxes:
            self.mailboxes[message.recipient].receive(message)
            print(f"✉ {message.sender} -> {message.recipient}: {message.subject}")

    def broadcast(self, message):
        for name, mailbox in self.mailboxes.items():
            if name != message.sender:
                mailbox.receive(message)
