"""Allow ``python -m cliprompt``."""

import sys

from .cli import main

sys.exit(main())
