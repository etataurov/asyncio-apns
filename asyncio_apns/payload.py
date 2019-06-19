from typing import Optional, List, Union


class PayloadAlert:
    def __init__(self,
                 title: Optional[str] = None,
                 title_localization_key: Optional[str] = None,
                 title_localization_args: Optional[List[str]] = None,
                 body: Optional[str] = None,
                 body_localization_key: Optional[str] = None,
                 body_localization_args: Optional[List[str]] = None,
                 action_localization_key: Optional[str] = None,
                 launch_image: Optional[str] = None
                 ):
        self.title = title
        self.title_localization_key = title_localization_key
        self.title_localization_args = title_localization_args
        self.body = body
        self.body_localization_key = body_localization_key
        self.body_localization_args = body_localization_args
        self.action_localization_key = action_localization_key
        self.launch_image = launch_image

    def as_dict(self):
        result = dict()
        if self.title is not None:
            result['title'] = self.title
        if self.title_localization_key is not None:
            result['title-loc-key'] = self.title_localization_key
        if self.title_localization_args is not None:
            result['title-loc-args'] = self.title_localization_args
        if self.body is not None:
            result['body'] = self.body
        if self.body_localization_key is not None:
            result['loc-key'] = self.body_localization_key
        if self.body_localization_args is not None:
            result['loc-args'] = self.body_localization_args
        if self.action_localization_key is not None:
            result['action-loc-key'] = self.action_localization_key
        if self.launch_image is not None:
            result['launch-image'] = self.launch_image
        return result


class Payload:
    def __init__(self,
                 alert: Optional[Union[PayloadAlert, str]] = None,
                 badge: Optional[int] = None,
                 sound: Optional[str] = None,
                 content_available: Optional[bool] = None,
                 category: Optional[str] = None,
                 custom: Optional[dict] = None):
        self.alert = alert
        self.badge = badge
        self.sound = sound
        self.content_available = content_available
        self.category = category
        self.custom = custom

    def as_dict(self):
        result = dict(aps={})
        aps_dict = result['aps']
        if self.alert is not None:
            if isinstance(self.alert, PayloadAlert):
                alert = self.alert.as_dict()
            else:
                alert = self.alert
            aps_dict['alert'] = alert
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
