from typing import Optional


class Payload:
    def __init__(self,
                 alert: Optional[str]=None,
                 badge: Optional[int]=None,
                 sound: Optional[str]=None,
                 content_available: Optional[bool]=None,
                 category: Optional[str]=None,
                 custom: Optional[dict]=None):
        self.alert = alert
        self.badge = badge
        self.sound = sound
        self.content_available = content_available
        self.category = category
        self.custom = custom
        # TODO: priority

    def as_dict(self):
        result = dict(aps={})
        aps_dict = result['aps']
        if self.alert is not None:
            aps_dict['alert'] = self.alert
        if self.badge is not None:
            aps_dict['badge'] = self.badge
        if self.sound is not None:
            aps_dict['sound'] = self.sound
        if self.content_available:
            aps_dict['content-available'] = 1
        if self.category is not None:
            aps_dict['category'] = self.category
        if self.custom is not None:
            result.update(self.custom)
        return result
