class ApnsError(Exception):
    def __init__(self, status, identifier):
        super().__init__()
        self.status = status
        self.identifier = identifier

    def __repr__(self):
        return "ApnsError(status={}, identifier={})".format(
            self.status, self.identifier)

    def __str__(self):
        # TODO description from Apple
        return "ApnsError({})".format(self.status)

    def message_was_sent(self):
        # 10 - shutdown
        return self.status == 10


class ApnsDisconnectError(Exception):
    pass
