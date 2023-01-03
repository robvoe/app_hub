import re
from typing import Tuple, Optional

_PATTERN_COMMAND_VALIDITY_CHECK = re.compile(r"^(§USER=[a-zA-Z0-9_]+§)?[^§]+$", flags=re.IGNORECASE)
_PATTERN_EXTRACT_USER_AND_COMMAND = re.compile(r"^§USER=([a-zA-Z0-9_]+)§([^§]+)$", flags=re.IGNORECASE)


def check_commandline_validity(commandline: str) -> bool:
    _match = _PATTERN_COMMAND_VALIDITY_CHECK.match(commandline)
    if _match is None:
        return False
    return True


def split_user_and_commandline(commandline: str) -> Tuple[Optional[str], str]:
    """
    Splits a commandline string into its constituents,
    e.g.  "§USER=my_user§python3 bla.py" -> ("my_user", "python3 bla.py")

    @return Returns a tuple that holds the user- and commandline-part of a singular commandline string. If no user
            argument is present, it will be None.
    """
    _match = _PATTERN_EXTRACT_USER_AND_COMMAND.match(commandline)
    if _match is None:
        return None, commandline
    _user, _cmd = _match.group(1), _match.group(2)
    return _user, _cmd
