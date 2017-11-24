
class McxError(Exception):
    """Basic exception for errors raised by mcx"""
    pass


class McxParsingError(McxError):
    """Basic exception for parsing errors raised by McxApi"""
    def __init__(self, json, msg=None):
        if msg is None:
            msg = "Unable to parse"
        super(McxParsingError, self).__init__(msg, original_exception)
        self.json = json


class McxNetworkError(McxError):
    """Basic exception for network errors raised by McxApi"""
    def __init__(self, url, msg=None, json=None):
        if msg is None:
            # Set some default useful error message
            msg = "Networking error for {} {}".format(url, json)
        super(McxNetworkError, self).__init__(msg)
        self.url = url
        self.json = json