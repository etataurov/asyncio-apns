class APNsError(Exception):
    def __init__(self, status, identifier):
        super().__init__()
        self.status = status
        self.identifier = identifier

    def __repr__(self):
        return "APNsError(status={}, identifier={})".format(
            self.status, self.identifier)

    def __str__(self):
        # TODO description from Apple
        return "APNsError({})".format(self.status)


class APNsDisconnectError(Exception):
    def __init__(self, reason):
        super().__init__()
        self.reason = reason
